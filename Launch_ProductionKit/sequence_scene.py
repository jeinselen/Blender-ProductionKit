import bpy
from bpy.app.handlers import persistent

# Sequence Scene: lock a workspace's Sequence view to the globally active scene.
#
# Blender stores the sequencer scene per workspace (WorkSpace.sequencer_scene), not per area,
# so the "follow" option is a workspace setting. To have one Sequence view stay on the main edit
# while another follows the active scene, put the follower in a separate window (with its own
# workspace) and enable the toggle there.

POLL_INTERVAL = 0.1



###########################################################################
# Scene sync

def _is_following(window):
	workspace = window.workspace
	return workspace is not None and getattr(workspace, "production_kit_follow_scene", False)


def _source_scene(window_manager):
	# Prefer the window the user is working in, then any window that isn't following
	window = bpy.context.window
	if window and not _is_following(window):
		return window.scene
	for window in window_manager.windows:
		if not _is_following(window):
			return window.scene
	# Every window follows, so each follows its own active scene
	return None


def _sync():
	window_manager = bpy.context.window_manager
	if window_manager is None:
		return False

	following = [w for w in window_manager.windows if _is_following(w)]
	if not following:
		return False

	source = _source_scene(window_manager)
	for window in following:
		target = source or window.scene
		workspace = window.workspace
		if target and workspace.sequencer_scene != target:
			workspace.sequencer_scene = target
			for area in window.screen.areas:
				if area.type == 'SEQUENCE_EDITOR':
					area.tag_redraw()
	return True


def _timer():
	try:
		active = _sync()
	except Exception:
		active = True
	# Stop polling once no workspace is following
	return POLL_INTERVAL if active else None


def _start_timer():
	if not bpy.app.timers.is_registered(_timer):
		bpy.app.timers.register(_timer, first_interval=0.0, persistent=True)


def _update_follow(self, context):
	if self.production_kit_follow_scene:
		_start_timer()


@persistent
def _on_load_post(*args):
	if any(getattr(ws, "production_kit_follow_scene", False) for ws in bpy.data.workspaces):
		_start_timer()



###########################################################################
# UI

def draw_header(self, context):
	if context.space_data.view_type not in {'SEQUENCER', 'SEQUENCER_PREVIEW'}:
		return
	workspace = context.workspace
	following = workspace.production_kit_follow_scene
	self.layout.prop(
		workspace,
		"production_kit_follow_scene",
		text="",
		icon='LINKED' if following else 'UNLINKED',
		toggle=True)



###########################################################################
# Registration

def register():
	bpy.types.WorkSpace.production_kit_follow_scene = bpy.props.BoolProperty(
		name="Follow Active Scene",
		description="Lock this workspace's Sequence view to the active scene of the main window (use a separate window to keep another Sequence view on the main edit)",
		default=False,
		update=_update_follow)
	bpy.types.SEQUENCER_HT_header.append(draw_header)
	if _on_load_post not in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.append(_on_load_post)
	# Resume if the current file already has following workspaces
	bpy.app.timers.register(_on_load_post, first_interval=0.1)


def unregister():
	if _on_load_post in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(_on_load_post)
	if bpy.app.timers.is_registered(_timer):
		bpy.app.timers.unregister(_timer)
	bpy.types.SEQUENCER_HT_header.remove(draw_header)
	del bpy.types.WorkSpace.production_kit_follow_scene
