import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { ContextCapsule, CapsuleSection, SectionKind, parseCapsule, serializeCapsule } from './binaryFormat';

export class CapsuleManager {
    private context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    initialize() {
        const capsulesPath = this.getCapsulesPath();
        if (capsulesPath && !fs.existsSync(capsulesPath)) {
            fs.mkdirSync(capsulesPath, { recursive: true });
        }
    }

    getCapsulesPath(): string | undefined {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            return undefined;
        }

        const config = vscode.workspace.getConfiguration('medicineCabinet');
        const relativePath = config.get<string>('capsulesPath', '.aura_context');

        return path.join(workspaceFolders[0].uri.fsPath, relativePath);
    }

    async createCapsule() {
        const projectName = await vscode.window.showInputBox({
            prompt: 'Enter project name',
            value: vscode.workspace.name || 'Unnamed Project'
        });

        if (!projectName) {return;}

        const summary = await vscode.window.showInputBox({
            prompt: 'Enter a brief summary',
            placeHolder: 'What are you working on?'
        });

        if (!summary) {return;}

        const capsule: ContextCapsule = {
            metadata: {
                project: projectName,
                summary: summary,
                author: this.getGitAuthor(),
                created_at: new Date(),
                branch: await this.getGitBranch()
            },
            sections: []
        };

        const capsulesPath = this.getCapsulesPath();
        if (!capsulesPath) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        const fileName = `${projectName.toLowerCase().replace(/\s+/g, '_')}.auractx`;
        const filePath = path.join(capsulesPath, fileName);

        const buffer = serializeCapsule(capsule);
        fs.writeFileSync(filePath, buffer);

        vscode.window.showInformationMessage(`Created capsule: ${fileName}`);
    }

    async setTaskObjective() {
        const capsulePath = await this.selectCapsule();
        if (!capsulePath) {return;}

        const objective = await vscode.window.showInputBox({
            prompt: 'Enter task objective',
            placeHolder: 'What is the current task?'
        });

        if (!objective) {return;}

        const buffer = fs.readFileSync(capsulePath);
        const capsule = parseCapsule(buffer);

        // Remove existing task_objective section
        capsule.sections = capsule.sections.filter(s => s.name !== 'task_objective');

        // Add new task_objective
        capsule.sections.push({
            name: 'task_objective',
            kind: SectionKind.TEXT,
            payload: Buffer.from(objective, 'utf8')
        });

        fs.writeFileSync(capsulePath, serializeCapsule(capsule));
        vscode.window.showInformationMessage('Task objective updated');
    }

    async addRelevantFiles() {
        const capsulePath = await this.selectCapsule();
        if (!capsulePath) {return;}

        const files = await vscode.window.showOpenDialog({
            canSelectMany: true,
            openLabel: 'Select relevant files'
        });

        if (!files || files.length === 0) {return;}

        const buffer = fs.readFileSync(capsulePath);
        const capsule = parseCapsule(buffer);

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const relativePaths = files.map(f => {
            if (workspaceFolder) {
                return path.relative(workspaceFolder.uri.fsPath, f.fsPath);
            }
            return f.fsPath;
        });

        // Remove existing relevant_files section
        capsule.sections = capsule.sections.filter(s => s.name !== 'relevant_files');

        // Add new relevant_files
        capsule.sections.push({
            name: 'relevant_files',
            kind: SectionKind.JSON,
            payload: Buffer.from(JSON.stringify(relativePaths), 'utf8')
        });

        fs.writeFileSync(capsulePath, serializeCapsule(capsule));
        vscode.window.showInformationMessage(`Added ${files.length} relevant files`);
    }

    async viewCapsule(item?: any) {
        let capsulePath: string | undefined;

        if (item && item.resourceUri) {
            capsulePath = item.resourceUri.fsPath;
        } else {
            capsulePath = await this.selectCapsule();
        }

        if (!capsulePath) {return;}

        const buffer = fs.readFileSync(capsulePath);
        const capsule = parseCapsule(buffer);

        const doc = await vscode.workspace.openTextDocument({
            content: this.formatCapsule(capsule),
            language: 'markdown'
        });

        vscode.window.showTextDocument(doc);
    }

    private formatCapsule(capsule: ContextCapsule): string {
        let output = `# Context Capsule\n\n`;
        output += `**Project:** ${capsule.metadata.project}\n`;
        output += `**Summary:** ${capsule.metadata.summary}\n`;
        output += `**Author:** ${capsule.metadata.author || 'N/A'}\n`;
        output += `**Created:** ${capsule.metadata.created_at.toISOString()}\n`;
        output += `**Branch:** ${capsule.metadata.branch || 'N/A'}\n\n`;

        for (const section of capsule.sections) {
            output += `## ${section.name}\n\n`;

            if (section.kind === SectionKind.TEXT) {
                output += `${section.payload.toString('utf8')}\n\n`;
            } else if (section.kind === SectionKind.JSON) {
                const data = JSON.parse(section.payload.toString('utf8'));
                output += `\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\`\n\n`;
            } else {
                output += `<Binary data, ${section.payload.length} bytes>\n\n`;
            }
        }

        return output;
    }

    private async selectCapsule(): Promise<string | undefined> {
        const capsulesPath = this.getCapsulesPath();
        if (!capsulesPath || !fs.existsSync(capsulesPath)) {
            vscode.window.showWarningMessage('No capsules directory found');
            return undefined;
        }

        const files = fs.readdirSync(capsulesPath)
            .filter(f => f.endsWith('.auractx'));

        if (files.length === 0) {
            vscode.window.showWarningMessage('No capsules found');
            return undefined;
        }

        const selected = await vscode.window.showQuickPick(files, {
            placeHolder: 'Select a capsule'
        });

        return selected ? path.join(capsulesPath, selected) : undefined;
    }

    private getGitAuthor(): string | undefined {
        try {
            const cp = require('child_process');
            const name = cp.execSync('git config user.name', { encoding: 'utf8' }).trim();
            return name || undefined;
        } catch {
            return undefined;
        }
    }

    private async getGitBranch(): Promise<string | undefined> {
        try {
            const cp = require('child_process');
            const branch = cp.execSync('git branch --show-current', { encoding: 'utf8' }).trim();
            return branch || undefined;
        } catch {
            return undefined;
        }
    }

    listCapsules(): string[] {
        const capsulesPath = this.getCapsulesPath();
        if (!capsulesPath || !fs.existsSync(capsulesPath)) {
            return [];
        }

        return fs.readdirSync(capsulesPath)
            .filter(f => f.endsWith('.auractx'))
            .map(f => path.join(capsulesPath, f));
    }
}
