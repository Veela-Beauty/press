// vite.config.ts
import path from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueJsx from "@vitejs/plugin-vue-jsx";
import frappeui from "frappe-ui/vite";
import pluginRewriteAll from "vite-plugin-rewrite-all";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import dotenv from "dotenv";
dotenv.config();
var vite_config_default = defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        outDir: "../press/public/dashboard",
        indexHtmlPath: "../press/www/dashboard.html",
        emptyOutDir: true,
        sourcemap: true
      }
    }),
    vue(),
    vueJsx(),
    pluginRewriteAll(),
    sentryVitePlugin({
      url: process.env.SENTRY_URL,
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      applicationKey: "press-dashboard",
      authToken: process.env.SENTRY_AUTH_TOKEN,
      errorHandler: (err) => console.warn(err)
    })
  ],
  server: {
    allowedHosts: true
  },
  resolve: {
    alias: {
      "@": path.resolve("/home/frappe/frappe-bench/apps/press/dashboard", "src")
    }
  },
  optimizeDeps: {
    include: [
      "feather-icons",
      "showdown",
      "highlight.js/lib/core",
      "interactjs"
    ]
  },
  build: {
    chunkSizeWarningLimit: 2e3
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImltcG9ydCBwYXRoIGZyb20gJ3BhdGgnO1xuaW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSc7XG5pbXBvcnQgdnVlIGZyb20gJ0B2aXRlanMvcGx1Z2luLXZ1ZSc7XG5pbXBvcnQgdnVlSnN4IGZyb20gJ0B2aXRlanMvcGx1Z2luLXZ1ZS1qc3gnO1xuaW1wb3J0IGZyYXBwZXVpIGZyb20gJ2ZyYXBwZS11aS92aXRlJztcbmltcG9ydCBwbHVnaW5SZXdyaXRlQWxsIGZyb20gJ3ZpdGUtcGx1Z2luLXJld3JpdGUtYWxsJztcbmltcG9ydCB7IHNlbnRyeVZpdGVQbHVnaW4gfSBmcm9tICdAc2VudHJ5L3ZpdGUtcGx1Z2luJztcbmltcG9ydCBkb3RlbnYgZnJvbSAnZG90ZW52JztcbmRvdGVudi5jb25maWcoKTtcblxuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcblx0cGx1Z2luczogW1xuXHRcdGZyYXBwZXVpKHtcblx0XHRcdGZyYXBwZVByb3h5OiB0cnVlLFxuXHRcdFx0bHVjaWRlSWNvbnM6IHRydWUsXG5cdFx0XHRqaW5qYUJvb3REYXRhOiB0cnVlLFxuXHRcdFx0YnVpbGRDb25maWc6IHtcblx0XHRcdFx0b3V0RGlyOiAnLi4vcHJlc3MvcHVibGljL2Rhc2hib2FyZCcsXG5cdFx0XHRcdGluZGV4SHRtbFBhdGg6ICcuLi9wcmVzcy93d3cvZGFzaGJvYXJkLmh0bWwnLFxuXHRcdFx0XHRlbXB0eU91dERpcjogdHJ1ZSxcblx0XHRcdFx0c291cmNlbWFwOiB0cnVlLFxuXHRcdFx0fSxcblx0XHR9KSxcblx0XHR2dWUoKSxcblx0XHR2dWVKc3goKSxcblx0XHRwbHVnaW5SZXdyaXRlQWxsKCksXG5cdFx0c2VudHJ5Vml0ZVBsdWdpbih7XG5cdFx0XHR1cmw6IHByb2Nlc3MuZW52LlNFTlRSWV9VUkwsXG5cdFx0XHRvcmc6IHByb2Nlc3MuZW52LlNFTlRSWV9PUkcsXG5cdFx0XHRwcm9qZWN0OiBwcm9jZXNzLmVudi5TRU5UUllfUFJPSkVDVCxcblx0XHRcdGFwcGxpY2F0aW9uS2V5OiAncHJlc3MtZGFzaGJvYXJkJyxcblx0XHRcdGF1dGhUb2tlbjogcHJvY2Vzcy5lbnYuU0VOVFJZX0FVVEhfVE9LRU4sXG5cdFx0XHRlcnJvckhhbmRsZXI6IChlcnIpID0+IGNvbnNvbGUud2FybihlcnIpLFxuXHRcdH0pLFxuXHRdLFxuXHRzZXJ2ZXI6IHtcblx0XHRhbGxvd2VkSG9zdHM6IHRydWUsXG5cdH0sXG5cdHJlc29sdmU6IHtcblx0XHRhbGlhczoge1xuXHRcdFx0J0AnOiBwYXRoLnJlc29sdmUoXCIvaG9tZS9mcmFwcGUvZnJhcHBlLWJlbmNoL2FwcHMvcHJlc3MvZGFzaGJvYXJkXCIsICdzcmMnKSxcblx0XHR9LFxuXHR9LFxuXHRvcHRpbWl6ZURlcHM6IHtcblx0XHRpbmNsdWRlOiBbXG5cdFx0XHQnZmVhdGhlci1pY29ucycsXG5cdFx0XHQnc2hvd2Rvd24nLFxuXHRcdFx0J2hpZ2hsaWdodC5qcy9saWIvY29yZScsXG5cdFx0XHQnaW50ZXJhY3RqcycsXG5cdFx0XSxcblx0fSxcblx0YnVpbGQ6IHtcblx0XHRjaHVua1NpemVXYXJuaW5nTGltaXQ6IDIwMDAsXG5cdH0sXG59KTtcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFBQSxPQUFPLFVBQVU7QUFDakIsU0FBUyxvQkFBb0I7QUFDN0IsT0FBTyxTQUFTO0FBQ2hCLE9BQU8sWUFBWTtBQUNuQixPQUFPLGNBQWM7QUFDckIsT0FBTyxzQkFBc0I7QUFDN0IsU0FBUyx3QkFBd0I7QUFDakMsT0FBTyxZQUFZO0FBQ25CLE9BQU8sT0FBTztBQUVkLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzNCLFNBQVM7QUFBQSxJQUNSLFNBQVM7QUFBQSxNQUNSLGFBQWE7QUFBQSxNQUNiLGFBQWE7QUFBQSxNQUNiLGVBQWU7QUFBQSxNQUNmLGFBQWE7QUFBQSxRQUNaLFFBQVE7QUFBQSxRQUNSLGVBQWU7QUFBQSxRQUNmLGFBQWE7QUFBQSxRQUNiLFdBQVc7QUFBQSxNQUNaO0FBQUEsSUFDRCxDQUFDO0FBQUEsSUFDRCxJQUFJO0FBQUEsSUFDSixPQUFPO0FBQUEsSUFDUCxpQkFBaUI7QUFBQSxJQUNqQixpQkFBaUI7QUFBQSxNQUNoQixLQUFLLFFBQVEsSUFBSTtBQUFBLE1BQ2pCLEtBQUssUUFBUSxJQUFJO0FBQUEsTUFDakIsU0FBUyxRQUFRLElBQUk7QUFBQSxNQUNyQixnQkFBZ0I7QUFBQSxNQUNoQixXQUFXLFFBQVEsSUFBSTtBQUFBLE1BQ3ZCLGNBQWMsQ0FBQyxRQUFRLFFBQVEsS0FBSyxHQUFHO0FBQUEsSUFDeEMsQ0FBQztBQUFBLEVBQ0Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNQLGNBQWM7QUFBQSxFQUNmO0FBQUEsRUFDQSxTQUFTO0FBQUEsSUFDUixPQUFPO0FBQUEsTUFDTixLQUFLLEtBQUssUUFBUSxrREFBa0QsS0FBSztBQUFBLElBQzFFO0FBQUEsRUFDRDtBQUFBLEVBQ0EsY0FBYztBQUFBLElBQ2IsU0FBUztBQUFBLE1BQ1I7QUFBQSxNQUNBO0FBQUEsTUFDQTtBQUFBLE1BQ0E7QUFBQSxJQUNEO0FBQUEsRUFDRDtBQUFBLEVBQ0EsT0FBTztBQUFBLElBQ04sdUJBQXVCO0FBQUEsRUFDeEI7QUFDRCxDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
