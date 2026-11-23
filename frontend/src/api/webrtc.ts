export type CredencialMedia = { url: string; credencial: string; reserva: string | null; bitrate?: number };
export type ConexionMedia = { pc: RTCPeerConnection; id: string; cerrar: () => void };

async function esperarIce(pc: RTCPeerConnection, signal: AbortSignal) {
  if (pc.iceGatheringState === "complete") return;
  await new Promise<void>((resolve, reject) => {
    const limpiar = () => { window.clearTimeout(timer); pc.removeEventListener("icegatheringstatechange", cambio); signal.removeEventListener("abort", abortar); };
    const cambio = () => { if (pc.iceGatheringState === "complete") { limpiar(); resolve(); } };
    const abortar = () => { limpiar(); reject(new DOMException("Cancelado", "AbortError")); };
    const timer = window.setTimeout(() => { limpiar(); reject(new Error("No se pudo preparar la conexion de red para el video")); }, 12000);
    pc.addEventListener("icegatheringstatechange", cambio); signal.addEventListener("abort", abortar, { once: true });
    if (signal.aborted) abortar(); else cambio();
  });
}

export async function conectarMedia(grant: CredencialMedia, signal: AbortSignal,
  opciones: { stream?: MediaStream; video?: HTMLVideoElement; alDesconectar?: () => void }): Promise<ConexionMedia> {
  const pc = new RTCPeerConnection({ iceServers: [] });
  let sesionUrl: string | null = null;
  const headers = { Authorization: `Bearer ${grant.credencial}` };
  let cerrada = false;
  const cerrar = () => {
    if (cerrada) return; cerrada = true;
    pc.onconnectionstatechange = null; pc.ontrack = null; pc.close();
    if (opciones.video) opciones.video.srcObject = null;
    if (sesionUrl) void fetch(sesionUrl, { method: "DELETE", headers, keepalive: true }).catch(() => undefined);
  };
  signal.addEventListener("abort", cerrar, { once: true });
  try {
    if (signal.aborted) throw new DOMException("Cancelado", "AbortError");
    if (opciones.stream) {
      for (const track of opciones.stream.getTracks()) {
        const sender = pc.addTrack(track, opciones.stream);
        if (track.kind === "video") {
          const params = sender.getParameters();
          if (!params.encodings?.length) params.encodings = [{}];
          params.encodings[0].maxBitrate = grant.bitrate || 1_200_000; params.encodings[0].maxFramerate = 24;
          await sender.setParameters(params);
        }
      }
    } else {
      pc.addTransceiver("video", { direction: "recvonly" }); pc.addTransceiver("audio", { direction: "recvonly" });
      pc.ontrack = evento => {
        if (cerrada || signal.aborted) return;
        if (opciones.video) {
          const stream = opciones.video.srcObject instanceof MediaStream ? opciones.video.srcObject : new MediaStream();
          stream.addTrack(evento.track); opciones.video.srcObject = stream;
          void opciones.video.play().catch(() => undefined);
        }
      };
    }
    pc.onconnectionstatechange = () => {
      if (["failed", "disconnected", "closed"].includes(pc.connectionState)) opciones.alDesconectar?.();
    };
    await pc.setLocalDescription(await pc.createOffer()); await esperarIce(pc, signal);
    const endpoint = new URL(grant.url, window.location.href);
    const respuesta = await fetch(endpoint, { method: "POST", headers: { ...headers, "Content-Type": "application/sdp" }, body: pc.localDescription!.sdp, signal });
    if (!respuesta.ok) throw new Error(respuesta.status === 409 ? "Ya hay otra transmision en este evento" : "El servidor rechazo la conexion. Revisa tu autorizacion o vuelve a intentar");
    const location = respuesta.headers.get("Location");
    const id = respuesta.headers.get("ID");
    if (!location || !id || !/^[a-f0-9-]{36}$/i.test(id)) throw new Error("El servidor de video no devolvio una sesion valida");
    const url = new URL(location, endpoint);
    if (url.origin !== endpoint.origin) throw new Error("Direccion de sesion de video inesperada");
    sesionUrl = url.href;
    await pc.setRemoteDescription({ type: "answer", sdp: await respuesta.text() });
    if (signal.aborted) throw new DOMException("Cancelado", "AbortError");
    if (pc.connectionState !== "connected") await new Promise<void>((resolve, reject) => {
      const limpiar = () => { window.clearTimeout(timer); pc.removeEventListener("connectionstatechange", cambio); signal.removeEventListener("abort", abortar); };
      const abortar = () => { limpiar(); reject(new DOMException("Cancelado", "AbortError")); };
      const cambio = () => {
        if (pc.connectionState === "connected") { limpiar(); resolve(); }
        else if (["failed", "closed"].includes(pc.connectionState)) { limpiar(); reject(new Error("Se interrumpio la conexion de video")); }
      };
      const timer = window.setTimeout(() => { limpiar(); reject(new Error("No se pudo establecer el video. Revisa tu red o intenta otra conexion")); }, 20000);
      pc.addEventListener("connectionstatechange", cambio); signal.addEventListener("abort", abortar, { once: true });
      if (signal.aborted) abortar(); else cambio();
    });
    return { pc, id, cerrar };
  } catch (err) { cerrar(); throw err; }
}
