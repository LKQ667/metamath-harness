import type { ClientContext } from "@deepseek-ai/dsh-client-runtime/client";
export declare const inject: readonly ["inputTriggers", "connection", "sessions", "slots", "remote", "conversation"];
export declare function apply(ctx: ClientContext): void;
