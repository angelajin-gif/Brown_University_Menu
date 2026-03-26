
  # 个性化大学食堂助手

  This is a code bundle for 个性化大学食堂助手. The original project is available at https://www.figma.com/design/2SfqGX7wLdmaaMHvlsej0P/%E4%B8%AA%E6%80%A7%E5%8C%96%E5%A4%A7%E5%AD%A6%E9%A3%9F%E5%A0%82%E5%8A%A9%E6%89%8B.

  ## Running the code

  Run `npm i` to install the dependencies.

  Run `npm run dev` to start the development server.

  ## Build

  This frontend uses Vite. Production build output is `dist/`.

  ```bash
  npm run build
  ```

  ## Cloudflare Pages

  Configure Cloudflare Pages to build from `Frontend/` and deploy only Vite output:

  - Root directory: `Frontend`
  - Build command: `npm run build`
  - Build output directory: `dist`
  - Environment variable: `VITE_API_BASE_URL=https://<your-railway-backend-domain>`

  Do not set build output to `Frontend` or `/`.
  
