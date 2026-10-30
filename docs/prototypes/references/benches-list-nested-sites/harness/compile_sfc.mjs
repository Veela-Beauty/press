// Compile SFCs with Vue's compiler (template + script) and fail on any error.
import { readFileSync } from 'node:fs';
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc';

let failed = 0;
for (const file of process.argv.slice(2)) {
	const { descriptor, errors } = parse(readFileSync(file, 'utf8'), { filename: file });
	const errs = [...errors];
	try {
		const script = compileScript(descriptor, { id: 'x', inlineTemplate: !!descriptor.scriptSetup });
		if (!descriptor.scriptSetup && descriptor.template) {
			const t = compileTemplate({ source: descriptor.template.content, filename: file, id: 'x' });
			errs.push(...t.errors);
		}
		if (!script.content) errs.push('empty script output');
	} catch (e) {
		errs.push(e.message);
	}
	console.log(`${errs.length ? 'FAIL' : 'ok  '}  ${file.split('/dashboard/src/')[1]}${errs.length ? ' -> ' + errs.join('; ') : ''}`);
	failed += errs.length ? 1 : 0;
}
process.exit(failed ? 1 : 0);
