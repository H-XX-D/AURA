import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { Tablet, TabletEntry, parseTablet, serializeTablet } from './binaryFormat';

export class TabletManager {
    private context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    initialize() {
        const tabletsPath = this.getTabletsPath();
        if (!fs.existsSync(tabletsPath)) {
            fs.mkdirSync(tabletsPath, { recursive: true });
        }
    }

    getTabletsPath(): string {
        const config = vscode.workspace.getConfiguration('medicineCabinet');
        let tabletsPath = config.get<string>('tabletsPath', '~/.aura/tablets');

        if (tabletsPath.startsWith('~')) {
            tabletsPath = path.join(os.homedir(), tabletsPath.slice(1));
        }

        return tabletsPath;
    }

    async createTablet() {
        const title = await vscode.window.showInputBox({
            prompt: 'Enter tablet title',
            placeHolder: 'e.g., "Bug Fix: Authentication"'
        });

        if (!title) {return;}

        const description = await vscode.window.showInputBox({
            prompt: 'Enter description',
            placeHolder: 'What was accomplished?'
        });

        if (!description) {return;}

        const tablet: Tablet = {
            metadata: {
                title: title,
                description: description,
                author: this.getGitAuthor(),
                tags: []
            },
            version: 1,
            created_at: new Date(),
            entries: []
        };

        const tabletsPath = this.getTabletsPath();
        const fileName = `${title.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')}.auratab`;
        const filePath = path.join(tabletsPath, fileName);

        const buffer = serializeTablet(tablet);
        fs.writeFileSync(filePath, buffer);

        vscode.window.showInformationMessage(`Created tablet: ${fileName}`);
    }

    async viewTablet(item?: any) {
        let tabletPath: string | undefined;

        if (item && item.resourceUri) {
            tabletPath = item.resourceUri.fsPath;
        } else {
            tabletPath = await this.selectTablet();
        }

        if (!tabletPath) {return;}

        const buffer = fs.readFileSync(tabletPath);
        const tablet = parseTablet(buffer);

        const doc = await vscode.workspace.openTextDocument({
            content: this.formatTablet(tablet),
            language: 'markdown'
        });

        vscode.window.showTextDocument(doc);
    }

    private formatTablet(tablet: Tablet): string {
        let output = `# Tablet: ${tablet.metadata.title}\n\n`;
        output += `**Description:** ${tablet.metadata.description}\n`;
        output += `**Author:** ${tablet.metadata.author || 'N/A'}\n`;
        output += `**Created:** ${tablet.created_at.toISOString()}\n`;
        output += `**Tags:** ${tablet.metadata.tags.join(', ') || 'None'}\n`;
        output += `**Entries:** ${tablet.entries.length}\n\n`;

        tablet.entries.forEach((entry, i) => {
            output += `## Entry ${i + 1}: ${entry.path}\n\n`;

            if (entry.notes) {
                output += `**Notes:**\n${entry.notes}\n\n`;
            }

            if (entry.diff) {
                output += `**Diff:**\n\`\`\`diff\n${entry.diff}\n\`\`\`\n\n`;
            }
        });

        return output;
    }

    private async selectTablet(): Promise<string | undefined> {
        const tabletsPath = this.getTabletsPath();
        if (!fs.existsSync(tabletsPath)) {
            vscode.window.showWarningMessage('No tablets directory found');
            return undefined;
        }

        const files = fs.readdirSync(tabletsPath)
            .filter(f => f.endsWith('.auratab'));

        if (files.length === 0) {
            vscode.window.showWarningMessage('No tablets found');
            return undefined;
        }

        const selected = await vscode.window.showQuickPick(files, {
            placeHolder: 'Select a tablet'
        });

        return selected ? path.join(tabletsPath, selected) : undefined;
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

    listTablets(): string[] {
        const tabletsPath = this.getTabletsPath();
        if (!fs.existsSync(tabletsPath)) {
            return [];
        }

        return fs.readdirSync(tabletsPath)
            .filter(f => f.endsWith('.auratab'))
            .map(f => path.join(tabletsPath, f));
    }
}
