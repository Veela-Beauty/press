// Port of upstream Frappe Cloud pages/servers/list/utils.ts dropBench, with the version
// upgrade warning and delete path of components/group/ReleaseGroupActionCell.vue onDropBench.
import { createDocumentResource } from 'frappe-ui'
import { toast } from 'vue-sonner'
import { confirmDialog } from '@/utils/components'

export async function dropBench(bench: any, onDropped?: () => void) {
	const releaseGroup = createDocumentResource({
		doctype: 'Release Group',
		name: bench.name,
		auto: false,
	})
	// The full doc carries linked_version_upgrade (computed in ReleaseGroup.get_doc).
	await releaseGroup.reload()

	let message = `Are you sure you want to drop the bench <b>${bench.title}</b>?`
	if (releaseGroup.doc?.linked_version_upgrade) {
		message = `
			<div class="mb-4 p-3 bg-yellow-50 border-l-4 border-yellow-400 text-yellow-800">
				<p class="font-semibold">Warning</p>
				<p class="mt-1">This bench was created for upgrading your site's version and dropping this will cancel the site upgrade as well.</p>
			</div>
			${message}
		`
	}

	confirmDialog({
		title: 'Drop Bench',
		message,
		fields: [
			{
				label: 'Please type the bench name to confirm',
				fieldname: 'confirmBenchName',
			},
		],
		primaryAction: {
			label: 'Drop',
			theme: 'red',
			onClick: ({ hide, values }) => {
				if (releaseGroup.delete.loading) return
				if (values.confirmBenchName !== bench.title) {
					throw new Error('Bench name does not match')
				}
				toast.promise(
					releaseGroup.delete.submit(null, {
						onSuccess: () => {
							hide()
							onDropped?.()
						},
					}),
					{
						loading: 'Dropping bench...',
						success: 'Bench dropped successfully',
						error: (error) =>
							error.messages?.length
								? error.messages.join('\n')
								: 'Failed to drop bench',
					},
				)
			},
		},
	})
}
