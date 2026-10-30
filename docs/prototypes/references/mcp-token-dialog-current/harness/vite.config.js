import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import frappeui from 'frappe-ui/vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
	plugins: [frappeui({ lucideIcons: true, frappeProxy: false, frappeTypes: false, jinjaBootData: false, buildConfig: false }), vue()],
	resolve: {
		alias: [{ find: /^frappe-ui$/, replacement: fileURLToPath(new URL('./src/frappe-ui-shim.js', import.meta.url)) }],
	},
	server: { port: 5199, strictPort: true },
});
