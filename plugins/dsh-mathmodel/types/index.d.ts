export declare const name = "dsh-mathmodel";
export declare const SUPPORTED_DSH_VERSION = "0.1.0-rc.6";
export declare function detectHarnessVersion(requireFrom?: string | URL): string | null;
export declare function assertCompatibleHarnessVersion(version?: string | null): string;
export declare function apply(): void;
export declare const MANUAL_VISION_LIMITS: Readonly<{ maxImages: number; maxImageBytes: number; maxTotalBytes: number }>;
export declare const MANUAL_VISION_PROMPT: string;
export declare class ManualVisionService {
  constructor(options?: { now?: () => number });
  stageDraftImages(input: { images: readonly { mediaType: string; data: string; name?: string }[]; workspace: string }): Promise<{ schema: 'dsh.mathmodel.manual-vision-stage/v1'; files: readonly { name: string; path: string; bytes: number }[] }>;
}
export interface MathModelCardField {
  readonly id: string;
  readonly label: string;
  readonly type: "select" | "multiselect" | "number" | "boolean" | "text" | "path" | "credential-status";
  readonly required?: boolean;
  readonly default?: unknown;
  readonly options?: readonly string[];
  readonly min?: number;
  readonly max?: number;
}
export interface MathModelCardV1 {
  readonly schema: "dsh.mathmodel.card/v1";
  readonly skill: string;
  readonly title: string;
  readonly summary: string;
  readonly category: string;
  readonly fields: readonly MathModelCardField[];
  readonly prompt: { readonly objective: string; readonly instructions: readonly string[] };
  readonly help: Record<string, string | readonly string[]>;
}
export declare function validateCard(raw: unknown): MathModelCardV1;
export declare function parseAndValidateCard(text: string, source?: string): MathModelCardV1;
export declare function renderCardPrompt(card: MathModelCardV1, submitted?: Record<string, unknown>): string;
export declare class CardRegistry {
  constructor(skillRoot: string);
  invalidate(): void;
  list(): Promise<readonly MathModelCardV1[]>;
  get(skill: string): Promise<MathModelCardV1 | null>;
}
export declare class MathModelCardsRemote {
  constructor(registry: CardRegistry);
  list(): Promise<{ schema: "dsh.mathmodel.cards/v1"; cards: readonly MathModelCardV1[] }>;
  render(skill: string, values: Record<string, unknown>): Promise<{ schema: "dsh.mathmodel.draft/v1"; skill: string; text: string }>;
}
export interface PreflightItem {
  readonly id: string;
  readonly label: string;
  readonly status: "available" | "degraded" | "missing";
  readonly path: string | null;
  readonly version: string | null;
  readonly guidance: string | null;
}
export interface PreflightReport {
  readonly schema: "dsh.mathmodel.preflight/v1";
  readonly status: "ready" | "attention";
  readonly checkedAt: string;
  readonly readonly: true;
  readonly items: readonly PreflightItem[];
}
export declare class PreflightService {
  constructor(options?: Record<string, unknown>);
  run(): Promise<PreflightReport>;
}
