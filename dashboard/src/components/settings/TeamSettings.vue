<template>
	<div class="p-5">
		<ObjectList :options="teamMembersListOptions"> </ObjectList>
	</div>
</template>

<script setup>
import { defineAsyncComponent, h, ref } from 'vue';
import { toast } from 'vue-sonner';
import { getTeam } from '../../data/team';
import { confirmDialog, renderDialog } from '../../utils/components';
import ObjectList from '../ObjectList.vue';
import UserWithAvatarCell from '../UserWithAvatarCell.vue';
import RoleCell from './RoleCell.vue';
import { getToastErrorMessage } from '../../utils/toast';

// Role catalog mirrors PRESS_ROLES in press/press/doctype/team/team_roles.py.
// Backend's get_team_manage_permissions returns my_role_level; we filter the
// dropdown to roles whose level <= caller's. If backend levels change, update
// here to match — this is the single UI-side source of truth.
const PRESS_ROLE_LEVELS = {
	'Platform Admin': 100,
	'DevOps Admin': 50,
	'Developer': 20,
	'DevOps User': 10,
	'Implementor': 10,
	'Viewer': 10,
};

function rolesAtOrBelow(level) {
	return Object.keys(PRESS_ROLE_LEVELS).filter(r => PRESS_ROLE_LEVELS[r] <= level);
}

const team = getTeam();
team.getTeamMembers.submit();
team.getTeamManagePermissions.submit();
const teamMembersListOptions = ref({
	onRowClick: () => {},
	rowHeight: 50,
	list: team.getTeamMembers,
	columns: [
		{
			label: 'User',
			type: 'Component',
			component: ({ row }) => {
				return h(UserWithAvatarCell, {
					avatarImage: row.user_image,
					fullName: row.full_name,
					email: row.email,
				});
			},
			width: 1,
		},
		{
			label: 'Role',
			type: 'Component',
			component: ({ row }) => {
				const perms = team.getTeamManagePermissions.data || {};
				const isOwner = row.name === team.doc.user;
				const canEdit = perms.change_role && !isOwner;
				return h(RoleCell, {
					currentRole: row.press_role || 'Viewer',
					allowedRoles: rolesAtOrBelow(perms.my_role_level || 0),
					disabled: !canEdit,
					onChange: (newRole) => {
						if (team.setTeamMemberRole.loading) return;
						toast.promise(
							team.setTeamMemberRole.submit({ member: row.name, new_role: newRole }),
							{
								loading: 'Updating role...',
								success: () => {
									team.getTeamMembers.submit();
									return 'Role updated';
								},
								error: (e) => getToastErrorMessage(e),
							},
						);
					},
				});
			},
			width: 0.7,
		},
	],
	rowActions({ row }) {
		let team = getTeam();
		if (row.name === team.doc.user || row.name === team.doc.user_info?.name)
			return [];
		return [
			{
				label: 'Remove Member',
				condition: () => {
					const perms = team.getTeamManagePermissions.data || {};
					return perms.remove && row.name !== team.doc.user;
				},
				onClick() {
					if (team.removeTeamMember.loading) return;
					confirmDialog({
						title: 'Remove Member',
						message: `Are you sure you want to remove <b>${row.full_name}</b> from the team?`,
						onSuccess({ hide }) {
							if (team.removeTeamMember.loading) return;
							toast.promise(
								team.removeTeamMember.submit({ member: row.name }),
								{
									loading: 'Removing Member...',
									success: () => {
										team.getTeamMembers.submit();
team.getTeamManagePermissions.submit();
										hide();
										return 'Member Removed';
									},
									error: (e) => getToastErrorMessage(e),
								},
							);
						},
					});
				},
			},
		];
	},
	actions() {
		return [
			{
				label: 'Settings',
				iconLeft: 'settings',
				onClick() {
					const TeamSettingsDialog = defineAsyncComponent(
						() => import('./TeamSettingsDialog.vue'),
					);
					renderDialog(h(TeamSettingsDialog));
				},
			},
			...(team.getTeamManagePermissions.data?.invite
				? [
						{
							label: 'Add Member',
							variant: 'solid',
							iconLeft: 'plus',
							onClick() {
								const InviteTeamMemberDialog = defineAsyncComponent(
									() => import('./InviteTeamMemberDialog.vue'),
								);
								renderDialog(h(InviteTeamMemberDialog));
							},
						},
				  ]
				: []),
		];
	},
});
</script>
