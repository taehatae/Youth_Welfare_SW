// Node의 기본 테스트 실행기로 기존 React/TypeScript 소스를 실행한다. 새 의존성은 없다.
import { registerHooks } from "node:module"
import { existsSync, readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import ts from "typescript"

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith(".") && context.parentURL) {
      for (const extension of [".ts", ".tsx"]) {
        const url = new URL(specifier + extension, context.parentURL)
        if (existsSync(url)) return { url: url.href, shortCircuit: true }
      }
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url.endsWith(".css")) return { format: "module", source: "export {}", shortCircuit: true }
    // 이미지 import는 Vite처럼 파일 경로 문자열로 바꾼다.
    if (/\.(png|jpe?g|webp|svg|gif)$/.test(url)) return { format: "module", source: `export default ${JSON.stringify(url)}`, shortCircuit: true }
    if (/\.tsx?$/.test(url)) {
      return {
        format: "module", shortCircuit: true,
        source: ts.transpileModule(readFileSync(fileURLToPath(url), "utf8"), {
          compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
        }).outputText,
      }
    }
    return nextLoad(url, context)
  },
})
