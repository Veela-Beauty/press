<template>
	<div class="rounded border border-blue-200 bg-blue-50 p-3 space-y-2">
		<div class="text-sm font-medium text-blue-900">
			No eligible Release Groups for this site yet.
		</div>
		<div class="text-xs text-blue-800">
			To move this site, you need another RG on the same server with all this
			site's apps. Pick a path below — both end with you coming back here to do
			the actual move.
		</div>
		<div class="flex flex-wrap gap-2 pt-1">
			<Button variant="solid" @click="onCloneClicked">
				<template #prefix>
					<FeatherIcon name="copy" class="h-4 w-4" />
				</template>
				Clone this site's bench (recommended)
			</Button>
			<Button @click="onOpenNewBench">
				<template #prefix>
					<FeatherIcon name="plus" class="h-4 w-4" />
				</template>
				Create a new bench
			</Button>
		</div>
		<div class="text-[11px] text-blue-700 pt-1">
			<strong>Clone</strong>: copies the current bench's apps (you'll choose
			full-clone-and-deploy vs RG-only-clone).<br />
			<strong>New bench</strong>: opens the New Bench wizard in a new tab
			(start from scratch).<br />
			After either, deploy the new RG, then reopen this dialog.
		</div>
	</div>
</template>

<script setup>
import { Button, FeatherIcon } from 'frappe-ui';

defineProps({
	currentReleaseGroup: { type: String, default: null },
	currentReleaseGroupTitle: { type: String, default: null },
});
const emit = defineEmits(['clone-clicked']);

function onCloneClicked() {
	emit('clone-clicked');
}

function onOpenNewBench() {
	window.open('/dashboard/groups/new', '_blank');
}
</script>
