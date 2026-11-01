import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

(
  self as unknown as { MonacoEnvironment: { getWorker: () => Worker } }
).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};
loader.config({ monaco });
monaco.editor.defineTheme("tutor-dark", {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "comment", foreground: "657383", fontStyle: "italic" },
    { token: "keyword", foreground: "C693D8" },
    { token: "string", foreground: "CDB68E" },
    { token: "number", foreground: "9CC9AB" },
    { token: "identifier", foreground: "C8D3E1" },
    { token: "type.identifier", foreground: "71C0B1" },
  ],
  colors: {
    "editor.background": "#14191F",
    "editor.foreground": "#CCD5E0",
    "editorLineNumber.foreground": "#4D5968",
    "editorLineNumber.activeForeground": "#BBC9DA",
    "editor.lineHighlightBackground": "#1B222B",
    "editor.selectionBackground": "#2C4659",
    "editorCursor.foreground": "#5DD2A1",
    "editorIndentGuide.background1": "#252F3C",
    "editorWidget.background": "#1B2430",
    "editorWidget.border": "#334155",
  },
});
monaco.languages.registerCompletionItemProvider("python", {
  provideCompletionItems(model, position) {
    const word = model.getWordUntilPosition(position);
    const range = {
      startLineNumber: position.lineNumber,
      endLineNumber: position.lineNumber,
      startColumn: word.startColumn,
      endColumn: word.endColumn,
    };
    return {
      suggestions: [
        {
          label: "enumerate",
          insertText: "enumerate(${1:items})",
          detail: "带索引遍历",
          kind: monaco.languages.CompletionItemKind.Function,
        },
        {
          label: "range",
          insertText: "range(${1:stop})",
          detail: "生成整数序列",
          kind: monaco.languages.CompletionItemKind.Function,
        },
        {
          label: "len",
          insertText: "len(${1:items})",
          detail: "获取序列长度",
          kind: monaco.languages.CompletionItemKind.Function,
        },
        {
          label: "for",
          insertText: "for ${1:item} in ${2:items}:\n    ${0:pass}",
          detail: "for 循环",
          kind: monaco.languages.CompletionItemKind.Snippet,
        },
        {
          label: "if",
          insertText: "if ${1:condition}:\n    ${0:pass}",
          detail: "条件判断",
          kind: monaco.languages.CompletionItemKind.Snippet,
        },
        {
          label: "def",
          insertText: "def ${1:function}(${2:args}):\n    ${0:pass}",
          detail: "定义函数",
          kind: monaco.languages.CompletionItemKind.Snippet,
        },
      ].map((item) => ({
        ...item,
        range,
        insertTextRules:
          monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      })),
    };
  },
});
export { monaco };
