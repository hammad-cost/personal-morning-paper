import { CopilotKit } from '@copilotkit/react-core/v2'
import '@copilotkit/react-core/v2/styles.css'
import { copilotApiKey } from './config'

// Option A from BLUEPRINT.md: Copilot Cloud public key, no runtime server.
// With publicApiKey and no runtimeUrl, CopilotKit v2 talks to Copilot Cloud.

function CopilotProvider({ children }) {
  return <CopilotKit publicApiKey={copilotApiKey}>{children}</CopilotKit>
}

export default CopilotProvider
