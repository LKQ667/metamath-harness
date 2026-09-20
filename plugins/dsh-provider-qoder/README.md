# DSH Qoder Subscription Plugin

English | [简体中文](./README_CN.md)

`dsh-provider-qoder` integrates your Qoder subscription into DeepSeek Harness (DSH), supporting text and image input, streaming text, reasoning content, and tool calls across Global and China Qoder services.

The plugin handles authentication and model communication, while tool execution, workspace operations, and permission management are handled by DSH.
This project is a community adapter plugin.

## Features

- Configure subscription access via Qoder Personal Access Token (PAT).
- Supports both Global (`global`) and China (`china`) services.
- Discovers available models for your account, allows selecting enabled models, and displays pricing multipliers and reasoning effort options when reported by the service.
- Supports streaming responses, reasoning content, multimodality, search, tool calls, and multi-turn interactions.
- View account information, quota, and reset dates in Settings.

## Installation

### Prerequisites

You will need a running DSH Web environment, an active Qoder subscription, and a PAT matching the selected service region. The DSH profile running the plugin must provide a managed credentials service; when configuring via the settings page, the credential storage must also be writable.

This package's dependency ranges are DSH packages `>=0.1.2-rc.1 <0.2`, Cordis `>=4.0.2 <5`, and React `^18.2.0`. The settings UI also depends on the host providing remote credential endpoints and settings slots—please use a DSH version equipped with these interfaces; the ranges above do not imply that every version has been tested.

### Install from npm

Run in your terminal:

```sh
dsh plugin --profile web add dsh-provider-qoder
```

## Configuration & Usage

### 1. Save Service Region and PAT

Open DSH Web, navigate to **Settings → Models**, locate the **Qoder Credentials** card at the bottom of the page, and click **Edit**.

| Service Region | Account Domain |
| --- | --- |
| Global (default) | `qoder.com` |
| China (CN) | `qoder.com.cn` |

Select the region matching your account, enter your Qoder PAT into the input box labeled **API Key**, and click **Save**.

### 2. Fetch and Select Models

1. After saving the PAT and service region, click **Edit** again.
2. Expand **Custom Settings** and click **Fetch Available Models**.
3. Select the models you want to enable (keep at least one), then click **Save**.
4. Select a Qoder model in the DSH model picker to start chatting.

Fetching models uses the **saved PAT and service region**. If you switch accounts or regions, you need to fetch models again. The initial model catalog is only a candidate reference; actual available models are subject to account query results. Model multipliers, reasoning effort options, and image-input capability are provided by Qoder and may not be available for all models.

The model picker refreshes Qoder metadata for enabled models when opened, with a five-minute cache after a successful fetch.

### 3. View Account & Quota

Open **Settings → Qoder** to view account and quota details.

## FAQ

### The plugin fails to start, or credentials cannot be saved

Ensure you have restarted the profile where the plugin was installed, and that the profile provides the DSH managed credentials service. If prompted that the storage is not writable, a writable credential store needs to be configured on the host side. The plugin does not read PATs from environment variables.

### PAT is saved, but model fetching or requests fail

Verify that the PAT is valid and matches the saved service region. If modified, save first before fetching models. The save action itself does not validate the token. If your account quota is exhausted, you will need to resolve your subscription quota first.

### Models remain unavailable after switching regions

Global and China model catalogs are stored separately. Switching regions does not automatically update your PAT or refetch that region's models; after saving the matching PAT, fetch and save the models for the selected region.

### Are requests automatically retried?

Model-generation retries are managed by DSH. To enable them, the running profile should include `@deepseek-ai/dsh-llm-retry`. The plugin reports empty responses, rate limits, server errors, timeouts, and transport errors using DSH's default retry policy; authentication, invalid requests, cancellations, quota issues, and protocol formatting errors are not retried by default. The Qoder transport may independently retry an idempotent model-catalog, subscriber-profile, or quota read once, but never retries a model-generation POST internally.

## Install from Source & Development

Run in an environment with Git, Node.js, and pnpm installed. Node.js must support the `--experimental-strip-types` and `--test-isolation=none` flags used by the project's test scripts.

```sh
git clone https://github.com/mo-n/dsh-provider-qoder.git
cd dsh-provider-qoder
pnpm install --frozen-lockfile
pnpm run build
```

Install the built repository directory into your DSH profile. The path below is a placeholder example; replace it with the actual absolute path:

```sh
dsh plugin --profile web add /absolute/path/to/dsh-provider-qoder
```

After restarting the profile, follow the configuration steps above. If running the CLI within a DSH source workspace, you can use `pnpm dsh` from that workspace.

For development, run watch mode in the plugin directory:

```sh
pnpm run dev
```

Before committing changes, run:

```sh
pnpm run check
```

This command runs non-UI mocked tests, builds the ESM package and type declarations, checks build artifacts, and previews the package tarball without sending real Qoder model requests or publishing npm packages.

## References

- [pi-provider-qoder](https://github.com/simonsmh/pi-provider-qoder) - Reference implementation for Qoder authentication, API communication, and protocol handling.

## Feedback

Please report issues via [GitHub Issues](https://github.com/mo-n/dsh-provider-qoder/issues) with the plugin and DSH versions, selected service region, reproduction steps, and sanitized error messages. Do not submit PATs, short-lived tokens, or personal account information.

This project is licensed under the MIT License.
