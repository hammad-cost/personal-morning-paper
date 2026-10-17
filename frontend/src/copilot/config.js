// Kept apart from CopilotProvider so checking the key doesn't load CopilotKit.

export const copilotApiKey = import.meta.env.VITE_COPILOTKIT_PUBLIC_API_KEY ?? ''

export const hasCopilot = () => copilotApiKey.trim() !== ''
