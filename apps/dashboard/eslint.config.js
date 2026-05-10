import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  {
    ignores: ["dist/", "node_modules/", "eslint.config.js", "vite.config.ts", "src/routeTree.gen.ts"],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        project: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-confusing-void-expression": "off",
      "@typescript-eslint/no-deprecated": "off",
      "@typescript-eslint/only-throw-error": "off",
      "@typescript-eslint/prefer-promise-reject-errors": "off",
      "@typescript-eslint/restrict-template-expressions": "off",
      "@typescript-eslint/return-await": "off",
      "@typescript-eslint/unbound-method": "off",
      "no-console": "warn",
    },
  }
);
