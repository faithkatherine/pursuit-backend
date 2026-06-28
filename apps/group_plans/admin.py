from django.contrib import admin
from .models import (
    GroupPlan,
    GroupPlanEvent,
    VoteInvitation,
    IndividualVoterSession,
    Vote
)


@admin.register(GroupPlan)
class GroupPlanAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'creator', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'creator__email', 'creator__first_name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('id', 'creator', 'name', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GroupPlanEvent)
class GroupPlanEventAdmin(admin.ModelAdmin):
    list_display = ('event', 'group_plan', 'added_by', 'ordering', 'added_at')
    list_filter = ('added_at', 'group_plan__status')
    search_fields = ('event__name', 'group_plan__name')
    readonly_fields = ('id', 'added_at')
    autocomplete_fields = ('event',)


@admin.register(VoteInvitation)
class VoteInvitationAdmin(admin.ModelAdmin):
    list_display = ('group_plan', 'share_token', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('group_plan__name', 'share_token')
    readonly_fields = ('id', 'share_token', 'created_at')


@admin.register(IndividualVoterSession)
class IndividualVoterSessionAdmin(admin.ModelAdmin):
    list_display = ('display_initial', 'voter_name', 'display_color', 'registered_user', 'first_seen_at')
    list_filter = ('display_color', 'first_seen_at')
    search_fields = ('voter_name', 'registered_user__email', 'session_token')
    readonly_fields = ('id', 'session_token', 'first_seen_at', 'last_seen_at')


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('voter_session', 'group_plan_event', 'direction', 'cast_at')
    list_filter = ('direction', 'cast_at')
    search_fields = ('voter_session__voter_name', 'group_plan_event__event__name')
    readonly_fields = ('id', 'cast_at')
