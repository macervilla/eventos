import axios from "axios";

import { cerrarSesion, obtenerTokenSesion } from "./sesion";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api-vps"
});

// interceptors.request: agrega el token de sesion a cada pedido al backend
api.interceptors.request.use((config) => {
  const token = obtenerTokenSesion();
  if (token && !config.headers.Authorization) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// interceptors.response: si el backend rechaza la sesion (vencida o invalida), se descarta
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401
        && !error.config?.url?.includes("/portal") && error.config?.url !== "/acceso/google") cerrarSesion();
    return Promise.reject(error);
  }
);
