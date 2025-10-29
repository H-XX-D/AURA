import * as vscode from 'vscode';
import * as path from 'path';
import { TabletManager } from '../tabletManager';

export class TabletTreeProvider implements vscode.TreeDataProvider<TabletItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<TabletItem | undefined | null> = new vscode.EventEmitter<TabletItem | undefined | null>();
    readonly onDidChangeTreeData: vscode.Event<TabletItem | undefined | null> = this._onDidChangeTreeData.event;

    constructor(private tabletManager: TabletManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: TabletItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: TabletItem): Thenable<TabletItem[]> {
        if (element) {
            return Promise.resolve([]);
        }

        const tablets = this.tabletManager.listTablets();
        return Promise.resolve(
            tablets.map(t => new TabletItem(
                path.basename(t),
                vscode.Uri.file(t),
                vscode.TreeItemCollapsibleState.None
            ))
        );
    }
}

class TabletItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly resourceUri: vscode.Uri,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = this.resourceUri.fsPath;
        this.contextValue = 'tablet';
        this.command = {
            command: 'medicineCabinet.viewTablet',
            title: 'View Tablet',
            arguments: [this]
        };
    }
}
