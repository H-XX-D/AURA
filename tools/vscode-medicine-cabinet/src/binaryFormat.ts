/**
 * Binary format utilities for Medicine Cabinet files
 */

export const CAPSULE_MAGIC = Buffer.from('AURACTX1', 'ascii');
export const TABLET_MAGIC = Buffer.from('AURATAB1', 'ascii');
export const CAPSULE_VERSION = 1;
export const TABLET_VERSION = 1;

export enum SectionKind {
    TEXT = 1,
    JSON = 2,
    BINARY = 3
}

export interface CapsuleMetadata {
    project: string;
    summary: string;
    author?: string;
    created_at: Date;
    branch?: string;
    revision?: string;
    extra?: Record<string, any>;
}

export interface CapsuleSection {
    name: string;
    kind: SectionKind;
    payload: Buffer;
}

export interface ContextCapsule {
    metadata: CapsuleMetadata;
    sections: CapsuleSection[];
}

export interface TabletMetadata {
    title: string;
    description: string;
    author?: string;
    tags: string[];
    extra?: Record<string, any>;
}

export interface TabletEntry {
    path: string;
    diff: string;
    notes: string;
}

export interface Tablet {
    metadata: TabletMetadata;
    version: number;
    created_at: Date;
    entries: TabletEntry[];
}

export class BinaryReader {
    private buffer: Buffer;
    private cursor: number = 0;

    constructor(buffer: Buffer) {
        this.buffer = buffer;
    }

    readUInt8(): number {
        const value = this.buffer.readUInt8(this.cursor);
        this.cursor += 1;
        return value;
    }

    readUInt16BE(): number {
        const value = this.buffer.readUInt16BE(this.cursor);
        this.cursor += 2;
        return value;
    }

    readUInt32BE(): number {
        const value = this.buffer.readUInt32BE(this.cursor);
        this.cursor += 4;
        return value;
    }

    readUInt64BE(): bigint {
        const value = this.buffer.readBigUInt64BE(this.cursor);
        this.cursor += 8;
        return value;
    }

    readString(): string {
        const length = this.readUInt32BE();
        const value = this.buffer.toString('utf8', this.cursor, this.cursor + length);
        this.cursor += length;
        return value;
    }

    readBytes(length: number): Buffer {
        const value = this.buffer.subarray(this.cursor, this.cursor + length);
        this.cursor += length;
        return value;
    }

    readMagic(expected: Buffer): boolean {
        const magic = this.readBytes(expected.length);
        return magic.equals(expected);
    }
}

export class BinaryWriter {
    private buffers: Buffer[] = [];

    writeUInt8(value: number): void {
        const buf = Buffer.allocUnsafe(1);
        buf.writeUInt8(value, 0);
        this.buffers.push(buf);
    }

    writeUInt16BE(value: number): void {
        const buf = Buffer.allocUnsafe(2);
        buf.writeUInt16BE(value, 0);
        this.buffers.push(buf);
    }

    writeUInt32BE(value: number): void {
        const buf = Buffer.allocUnsafe(4);
        buf.writeUInt32BE(value, 0);
        this.buffers.push(buf);
    }

    writeUInt64BE(value: bigint): void {
        const buf = Buffer.allocUnsafe(8);
        buf.writeBigUInt64BE(value, 0);
        this.buffers.push(buf);
    }

    writeString(value: string): void {
        const strBuf = Buffer.from(value, 'utf8');
        this.writeUInt32BE(strBuf.length);
        this.buffers.push(strBuf);
    }

    writeBytes(value: Buffer): void {
        this.buffers.push(value);
    }

    toBuffer(): Buffer {
        return Buffer.concat(this.buffers);
    }
}

export function parseCapsule(buffer: Buffer): ContextCapsule {
    const reader = new BinaryReader(buffer);

    if (!reader.readMagic(CAPSULE_MAGIC)) {
        throw new Error('Invalid capsule magic header');
    }

    const version = reader.readUInt16BE();
    if (version !== CAPSULE_VERSION) {
        throw new Error(`Unsupported capsule version ${version}`);
    }

    const createdMs = reader.readUInt64BE();
    const createdAt = new Date(Number(createdMs));

    const metadataJson = reader.readString();
    const metadata: CapsuleMetadata = JSON.parse(metadataJson);
    metadata.created_at = createdAt;

    const sectionCount = reader.readUInt32BE();
    const sections: CapsuleSection[] = [];

    for (let i = 0; i < sectionCount; i++) {
        const name = reader.readString();
        const kind = reader.readUInt8() as SectionKind;
        const payloadLength = reader.readUInt32BE();
        const payload = reader.readBytes(payloadLength);

        sections.push({ name, kind, payload });
    }

    return { metadata, sections };
}

export function serializeCapsule(capsule: ContextCapsule): Buffer {
    const writer = new BinaryWriter();

    writer.writeBytes(CAPSULE_MAGIC);
    writer.writeUInt16BE(CAPSULE_VERSION);
    writer.writeUInt64BE(BigInt(capsule.metadata.created_at.getTime()));

    const metadataJson = JSON.stringify({
        project: capsule.metadata.project,
        summary: capsule.metadata.summary,
        author: capsule.metadata.author,
        branch: capsule.metadata.branch,
        revision: capsule.metadata.revision,
        extra: capsule.metadata.extra || {}
    });
    writer.writeString(metadataJson);

    writer.writeUInt32BE(capsule.sections.length);

    for (const section of capsule.sections) {
        writer.writeString(section.name);
        writer.writeUInt8(section.kind);
        writer.writeUInt32BE(section.payload.length);
        writer.writeBytes(section.payload);
    }

    return writer.toBuffer();
}

export function parseTablet(buffer: Buffer): Tablet {
    const reader = new BinaryReader(buffer);

    if (!reader.readMagic(TABLET_MAGIC)) {
        throw new Error('Invalid tablet magic header');
    }

    const version = reader.readUInt16BE();
    if (version !== TABLET_VERSION) {
        throw new Error(`Unsupported tablet version ${version}`);
    }

    const createdMs = reader.readUInt64BE();
    const createdAt = new Date(Number(createdMs));

    const metadataJson = reader.readString();
    const metadata: TabletMetadata = JSON.parse(metadataJson);

    const entryCount = reader.readUInt32BE();
    const entries: TabletEntry[] = [];

    for (let i = 0; i < entryCount; i++) {
        const path = reader.readString();
        const diff = reader.readString();
        const notes = reader.readString();

        entries.push({ path, diff, notes });
    }

    return { metadata, version, created_at: createdAt, entries };
}

export function serializeTablet(tablet: Tablet): Buffer {
    const writer = new BinaryWriter();

    writer.writeBytes(TABLET_MAGIC);
    writer.writeUInt16BE(tablet.version);
    writer.writeUInt64BE(BigInt(tablet.created_at.getTime()));

    const metadataJson = JSON.stringify({
        title: tablet.metadata.title,
        description: tablet.metadata.description,
        author: tablet.metadata.author,
        tags: tablet.metadata.tags,
        extra: tablet.metadata.extra || {}
    });
    writer.writeString(metadataJson);

    writer.writeUInt32BE(tablet.entries.length);

    for (const entry of tablet.entries) {
        writer.writeString(entry.path);
        writer.writeString(entry.diff);
        writer.writeString(entry.notes);
    }

    return writer.toBuffer();
}
