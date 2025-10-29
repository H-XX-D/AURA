import * as vscode from 'vscode';
import { CapsuleManager } from './capsuleManager';
import { TabletManager } from './tabletManager';
import { CapsuleTreeProvider } from './views/capsuleTreeProvider';
import { TabletTreeProvider } from './views/tabletTreeProvider';

export function activate(context: vscode.ExtensionContext) {
    console.log('Medicine Cabinet extension is now active');

    const capsuleManager = new CapsuleManager(context);
    const tabletManager = new TabletManager(context);

    // Register tree view providers
    const capsuleTreeProvider = new CapsuleTreeProvider(capsuleManager);
    const tabletTreeProvider = new TabletTreeProvider(tabletManager);

    vscode.window.registerTreeDataProvider('capsules', capsuleTreeProvider);
    vscode.window.registerTreeDataProvider('tablets', tabletTreeProvider);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.createCapsule', async () => {
            await capsuleManager.createCapsule();
            capsuleTreeProvider.refresh();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.createTablet', async () => {
            await tabletManager.createTablet();
            tabletTreeProvider.refresh();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.viewCapsule', async (item) => {
            await capsuleManager.viewCapsule(item);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.viewTablet', async (item) => {
            await tabletManager.viewTablet(item);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.setTaskObjective', async () => {
            await capsuleManager.setTaskObjective();
            capsuleTreeProvider.refresh();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.addRelevantFiles', async () => {
            await capsuleManager.addRelevantFiles();
            capsuleTreeProvider.refresh();
        })
    );

    // Register refresh commands
    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.refreshCapsules', () => {
            capsuleTreeProvider.refresh();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('medicineCabinet.refreshTablets', () => {
            tabletTreeProvider.refresh();
        })
    );

    // Initialize - create directories if they don't exist
    capsuleManager.initialize();
    tabletManager.initialize();
}

export function deactivate() {
    console.log('Medicine Cabinet extension is now deactivated');
}
