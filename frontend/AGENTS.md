# Interacciones de la interfaz

- No usar los dialogos nativos del navegador: `alert`, `confirm` ni `prompt` (incluidas sus variantes `window.*`).
- Mostrar confirmaciones y alertas en ventanas popup de la aplicacion, con titulo, mensaje y botones especificos para cada caso.
- Para confirmaciones usar `useConfirmacion`; para formularios o avisos personalizados usar `Ventana`.
- Cancelar, Escape o cerrar una confirmacion no debe ejecutar la accion. Validar los datos antes de enviar un formulario.
