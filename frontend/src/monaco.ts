import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";
import "monaco-editor/esm/vs/basic-languages/java/java.contribution";
import "monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution";
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
// Local snippets and current-document word suggestions provide a useful
// baseline. No remote language server or IDE-level semantic analysis is used.
const languageSnippets = {
  java: [
    ["for", "for (int ${1:i} = 0; ${1:i} < ${2:count}; ${1:i}++) {\n    $0\n}", "索引循环"],
    ["if", "if (${1:condition}) {\n    $0\n}", "条件判断"],
    ["ArrayList", "ArrayList<${1:Integer}> ${2:items} = new ArrayList<>();", "动态数组（需 java.util）"],
    ["HashMap", "HashMap<${1:Integer}, ${2:Integer}> ${3:map} = new HashMap<>();", "哈希表（需 java.util）"],
  ],
  c: [
    ["for", "for (int ${1:i} = 0; ${1:i} < ${2:count}; ${1:i}++) {\n    $0\n}", "索引循环"],
    ["if", "if (${1:condition}) {\n    $0\n}", "条件判断"],
    ["malloc", "malloc(sizeof(${1:int}) * ${2:count})", "分配内存（需 stdlib.h），检查返回值并释放"],
    ["free", "free(${1:pointer});", "释放内存（需 stdlib.h）"],
  ],
  cpp: [
    ["for", "for (const auto& ${1:item} : ${2:items}) {\n    $0\n}", "范围循环"],
    ["if", "if (${1:condition}) {\n    $0\n}", "条件判断"],
    ["vector", "std::vector<${1:int}> ${2:items};", "动态数组（需 vector）"],
    ["unordered_map", "std::unordered_map<${1:int}, ${2:int}> ${3:map};", "哈希表（需 unordered_map）"],
    ["sort", "std::sort(${1:items}.begin(), ${1:items}.end());", "排序（需 algorithm）"],
  ],
};
Object.entries(languageSnippets).forEach(([language, snippets]) => {
  monaco.languages.registerCompletionItemProvider(language, {
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position);
      return {
        suggestions: snippets.map(([label, insertText, detail]) => ({
          label,
          insertText,
          detail,
          kind: monaco.languages.CompletionItemKind.Snippet,
          range: { startLineNumber: position.lineNumber, endLineNumber: position.lineNumber, startColumn: word.startColumn, endColumn: word.endColumn },
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        })),
      };
    },
  });
});
export { monaco };
