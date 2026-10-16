export const eventTemplates = {
  classic: {
    label: "Clasico",
    description: "Equilibrado, claro y versatil para cualquier evento.",
    className: "event-template-classic",
    swatches: ["#285C50", "#D98B6C", "#F7F5F0"]
  },
  elegant: {
    label: "Elegante",
    description: "Sobrio, editorial y refinado.",
    className: "event-template-elegant",
    swatches: ["#1D2A2A", "#B08D57", "#F6F0E8"]
  },
  party: {
    label: "Fiesta",
    description: "Colorido, dinamico y celebratorio.",
    className: "event-template-party",
    swatches: ["#7C3AED", "#F97316", "#FFF7ED"]
  },
  kids: {
    label: "Infantil",
    description: "Suave, alegre y familiar.",
    className: "event-template-kids",
    swatches: ["#2F80ED", "#F2C94C", "#FDF6E8"]
  },
  sport: {
    label: "Deportivo",
    description: "Energia, contraste y accion.",
    className: "event-template-sport",
    swatches: ["#163B33", "#E23D28", "#F3F5F0"]
  },
  minimal: {
    label: "Minimal",
    description: "Limpio, silencioso y centrado en contenido.",
    className: "event-template-minimal",
    swatches: ["#111827", "#6B7280", "#FAFAFA"]
  },
  dark: {
    label: "Oscuro",
    description: "Intenso, nocturno y moderno.",
    className: "event-template-dark",
    swatches: ["#101820", "#D98B6C", "#1F2933"]
  }
};

export const providerTemplates = {
  professional: {
    label: "Profesional",
    description: "Claro, confiable y orientado a servicios.",
    className: "provider-template-professional",
    swatches: ["#285C50", "#D98B6C", "#F7F5F0"]
  },
  elegant: {
    label: "Elegante",
    description: "Premium, sobrio y editorial.",
    className: "provider-template-elegant",
    swatches: ["#1D2A2A", "#B08D57", "#F6F0E8"]
  },
  creative: {
    label: "Creativo",
    description: "Expresivo, visual y cercano.",
    className: "provider-template-creative",
    swatches: ["#315C8C", "#D98B6C", "#F7F1E8"]
  },
  dark: {
    label: "Oscuro",
    description: "Alto contraste para marcas nocturnas.",
    className: "provider-template-dark",
    swatches: ["#111827", "#D98B6C", "#26313D"]
  },
  minimal: {
    label: "Minimal",
    description: "Directo, simple y liviano.",
    className: "provider-template-minimal",
    swatches: ["#202124", "#8A8F98", "#FFFFFF"]
  },
  photographic: {
    label: "Fotografico",
    description: "Ideal para galerias e imagen protagonista.",
    className: "provider-template-photographic",
    swatches: ["#243A3A", "#C78665", "#EFE8DD"]
  }
};

export type EventTemplateKey = keyof typeof eventTemplates;
export type ProviderTemplateKey = keyof typeof providerTemplates;
