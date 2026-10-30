// Port of upstream Frappe Cloud pages/servers/list/utils.ts dropBench; same delete path as
// components/group/ReleaseGroupActionCell.vue onDropBench.
import { createDocumentResource } from 'frappe-ui'
import { toast } from 'vue-sonner'
import { confirmDialog } from '@/utils/components'

export function dropBench(bench: any) {
  const releaseGroup = createDocumentResource({
    doctype: 'Release Group',
    name: bench.name,
  })

	confirmDialog({
		title: 'Drop Bench',
		message: `Are you sure you want to drop the bench <b>${bench.title}</b>?`,
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
