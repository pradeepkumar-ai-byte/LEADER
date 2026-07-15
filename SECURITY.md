# Security Policy

## Credential Handling

Leader is designed to be **credential-aware** — it handles API keys and tokens for multiple backend services. Here's how we keep your credentials safe:

### How Leader Protects Your Keys

1. **Environment Variable Priority**: Leader checks environment variables before reading the config file. Set your keys as environment variables to avoid writing them to disk at all.

2. **Restricted File Permissions**: When `leader init` creates `~/.leader/config.yaml`, it sets file permissions to `600` (owner read/write only) on Unix/macOS systems.

3. **No Credential Logging**: API keys are never written to `history.db` or any log output.

4. **No Network Transmission**: Leader never sends your credentials anywhere except to the backend they belong to.

### Recommended Setup

```bash
# Set credentials as environment variables (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export OPENROUTER_API_KEY="sk-or-..."

# Or use the config file (auto-secured with restricted permissions)
leader init
```

### Environment Variables

Leader supports the following environment variables:

| Variable | Used By |
|----------|---------|
| `ANTHROPIC_API_KEY` | Direct LLM (Anthropic/Claude) |
| `OPENAI_API_KEY` | Direct LLM (OpenAI/GPT) |
| `OPENROUTER_API_KEY` | Direct LLM (OpenRouter) |
| `LEADER_API_KEY_{BACKEND_ID}` | Any backend (e.g., `LEADER_API_KEY_OPENCLAW`) |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly (see README for contact)
3. Include a description of the vulnerability and steps to reproduce
4. Allow 48 hours for an initial response

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅         |
