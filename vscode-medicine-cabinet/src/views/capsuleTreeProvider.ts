import * as vscode from 'vscode';
import * as path from 'path';
import { CapsuleManager } from '../capsuleManager';

export class CapsuleTreeProvider implements vscode.TreeDataProvider<CapsuleItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<CapsuleItem | undefined | null> = new vscode.EventEmitter<CapsuleItem | undefined | null>();
    readonly onDidChangeTreeData: vscode.Event<CapsuleItem | undefined | null> = this._onDidChangeTreeData.event;

    constructor(private capsuleManager: CapsuleManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: CapsuleItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: CapsuleItem): Thenable<CapsuleItem[]> {
        if (element) {
            return Promise.resolve([]);
        }

        const capsules = this.capsuleManager.listCapsules();
        return Promise.resolve(
            capsules.map(c => new CapsuleItem(
                path.basename(c),
                vscode.Uri.file(c),
                vscode.TreeItemCollapsibleState.None
            ))
        );
    }
}

class CapsuleItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly resourceUri: vscode.Uri,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = this.resourceUri.fsPath;
        this.contextValue = 'capsule';
        this.command = {
            command: 'medicineCabinet.viewCapsule',
            title: 'View Capsule',
            arguments: [this]
        };
    }
}
