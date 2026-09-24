<template>
	<Dialog :options="{ title: 'Switch Team' }" v-model="show">
		<template #body-content v-if="$team?.doc">
			<div class="rounded bg-gray-100 px-3 py-2.5">
				<div class="text-base text-gray-900">
					You are logged in as the user
					<span class="font-medium">{{ $session.user }}</span>
				</div>
				<div class="mt-2 text-base text-gray-900">
					You are viewing dashboard for the team
					<component
						:is="$team.doc.is_desk_user ? 'a' : 'span'"
						class="font-medium"
						:class="{ underline: $team.doc.is_desk_user }"
						:href="$team.doc.is_desk_user ? `/app/team/${$team.name}` : null"
						target="_blank"
					>
						{{ $team.doc.team_title || $team.doc.user }}
					</component>
				</div>
			</div>
			<div class="mt-3">
				<TextInput
					v-if="sortedTeams.length > 5"
					size="sm"
					placeholder="Search"
					:debounce="500"
					v-model="searchQuery"
				/>
			</div>
			<div class="-mb-3 mt-3 divide-y">
				<div
					class="flex items-center justify-between py-3"
					v-for="team in filteredTeams"
					:key="team.name"
				>
					<div class="flex items-center space-x-2">
						<div>
							<div class="text-base text-gray-800">{{ teamLabel(team) }}</div>
							<div
								v-if="teamLabel(team) !== team.user"
								class="mt-0.5 text-sm text-gray-600"
							>
								{{ team.user }}
							</div>
						</div>
						<Button
							v-if="$team.doc.is_desk_user"
							icon="external-link"
							:link="`/app/team/${team.name}`"
							variant="ghost"
						/>
					</div>
					<Badge
						class="whitespace-nowrap"
						v-if="$team.name === team.name"
						label="Currently Active"
						theme="green"
					/>
					<Button v-else @click="switchToTeam(team.name)">Switch</Button>
				</div>
			</div>
			<div class="mt-6 flex items-end gap-2" v-if="$session.isSystemUser">
				<LinkControl
					class="w-full"
					label="Select Team"
					:options="{ doctype: 'Team', filters: { enabled: 1 } }"
					v-model="selectedTeam"
					description="This feature is only available to system users"
				/>
				<div class="pb-5">
					<Button :disabled="!selectedTeam" @click="switchToTeam(selectedTeam)">
						Switch
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script>
import { TextInput, call } from 'frappe-ui';
import { switchToTeam } from '../data/team';
import LinkControl from './LinkControl.vue';

export default {
	name: 'SwitchTeamDialog',
	props: ['modelValue'],
	emits: ['update:modelValue'],
	components: { LinkControl, TextInput },
	computed: {
		show: {
			get() {
				return this.modelValue;
			},
			set(value) {
				this.$emit('update:modelValue', value);
			},
		},
		sortedTeams() {
			if (!this.$team?.doc?.valid_teams) return [];
			return [...this.$team.doc.valid_teams].sort((a, b) =>
				this.teamLabel(a).localeCompare(this.teamLabel(b)),
			);
		},
		filteredTeams() {
			if (!this.searchQuery.trim()) {
				return this.sortedTeams;
			}
			const query = this.searchQuery.toLowerCase();
			return this.sortedTeams.filter(
				(team) =>
					this.teamLabel(team).toLowerCase().includes(query) ||
					team.user.toLowerCase().includes(query) ||
					team.name.toLowerCase().includes(query),
			);
		},
	},
	watch: {
		show: {
			immediate: true,
			handler(open) {
				if (open) this.loadTeamTitles();
			},
		},
	},
	data() {
		return {
			selectedTeam: null,
			searchQuery: '',
			teamTitles: {},
		};
	},
	methods: {
		switchToTeam,
		teamLabel(team) {
			return this.teamTitles[team.name] || team.user;
		},
		async loadTeamTitles() {
			// valid_teams carries only the owner email, so two teams one user owns read the same
			const names = (this.$team?.doc?.valid_teams || []).map((t) => t.name);
			if (!this.$session.isSystemUser || names.length < 2) return;
			try {
				const rows = await call('press.api.client.search_link', {
					doctype: 'Team',
					filters: { name: ['in', names] },
					page_length: names.length,
				});
				this.teamTitles = Object.fromEntries(rows.map((r) => [r.value, r.label]));
			} catch (e) {
				console.error('Could not load team titles, showing owner emails', e);
			}
		},
	},
};
</script>
