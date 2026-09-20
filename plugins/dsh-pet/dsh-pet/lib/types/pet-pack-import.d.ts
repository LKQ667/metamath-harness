export interface PetPackUploadFile {
    path: string;
    data: string;
}
export interface PetPackUploadPayload {
    files?: PetPackUploadFile[];
}
export interface PetPackImportOptions {
    petDir: string;
    existingPetIds: ReadonlySet<string>;
}
export interface PetPackImportResult {
    prefix: string;
    petCount: number;
    animationCount: number;
}
export declare class PetPackImportError extends Error {
    constructor(message: string, status?: number);
    get status(): number;
}
export declare function importPetPack(payload: PetPackUploadPayload, options: PetPackImportOptions): Promise<PetPackImportResult>;
