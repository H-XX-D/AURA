# Medicine Cabinet - VS Code Extension

AI Agent Memory System for Visual Studio Code

## Features

- **Context Capsules**: Store project-specific working memory
- **Tablets**: Store long-term, portable knowledge 
- **Binary Format**: Efficient, structured storage
- **Tree Views**: Browse capsules and tablets in the sidebar
- **Quick Commands**: Create and manage memory files

## Usage

### Creating a Context Capsule

1. Open Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`)
2. Run `Medicine Cabinet: Create Context Capsule`
3. Enter project name and summary
4. Capsule is saved to `.aura_context/` in your workspace

### Setting Task Information

1. Run `Medicine Cabinet: Set Task Objective`
2. Select a capsule
3. Enter your current task objective

### Creating a Tablet

1. Run `Medicine Cabinet: Create Tablet`
2. Enter title and description
3. Tablet is saved to `~/.aura/tablets/`

### Viewing Files

- Click on any capsule or tablet in the sidebar to view its contents
- Files are displayed in a readable markdown format

## Configuration

- `medicineCabinet.capsulesPath`: Location for context capsules (default: `.aura_context`)
- `medicineCabinet.tabletsPath`: Location for tablets (default: `~/.aura/tablets`)
- `medicineCabinet.autoSave`: Auto-save context changes (default: `true`)

## Requirements

- VS Code 1.80.0 or higher

## Installation

### From VSIX

1. Download the `.vsix` file
2. Open VS Code
3. Go to Extensions view
4. Click the `...` menu
5. Select "Install from VSIX..."
6. Choose the downloaded file

### From Source

```bash
cd vscode-medicine-cabinet
npm install
npm run compile
```

## License

MIT License - see LICENSE file

## Author

Todd Hendricks

## Related Projects

- [Medicine Cabinet Python Library](https://github.com/hendrixx-cnc/AURA/tree/main/medicine_cabinet)
- [AURA Compression](https://github.com/hendrixx-cnc/AURA)
- [Orkestra](https://github.com/hendrixx-cnc/Orkestra)
