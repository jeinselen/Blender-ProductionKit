import bpy
from bpy.app.handlers import persistent
import random

###########################################################################
# Main class

class SetVertexLocationKeyframes(bpy.types.Operator):
	bl_idname = "anim.set_vertex_location_keyframes"
	bl_label = "Create Keyframes"
	bl_description = "Create location keyframes for each target item"
	
	def execute(self, context):
		settings = context.scene.production_kit_settings
		
		# self.report({'INFO'}, f"This is {self.bl_idname}")
		if not context.view_layer.objects.active.data.vertices:
			return {'CANCELLED'}
		
		startFrame = context.scene.frame_current
		source = context.view_layer.objects.active.data.vertices
		objWorld = context.view_layer.objects.active.matrix_world
		
		# The active item may or may not be in the selected items group, so we have to make sure we don't include it in our targets
		targets = []
		for i in range(len(context.view_layer.objects.selected)):
			if context.view_layer.objects.selected[i].name != context.view_layer.objects.active.name:
				targets.append(context.view_layer.objects.selected[i])
		length = min(len(source), len(targets))
		
		# Randomise the order of the object orders
		order = [*range(length)]
		if settings.vertex_location_shuffle_order:
			random.shuffle(order)
		
		# Randomise the order of the object timing offsets
		timing = [*range(length)]
		if settings.vertex_location_shuffle_timing:
			random.shuffle(timing)
		
		# Loop through all of the vertices or objects (whichever is shorter)
		for i in range(length):
			offsetFrame = startFrame + (timing[i] * settings.vertex_location_keyframe_offset)
			# Transform vertex locations to world space
			if settings.vertex_location_world_space:
				co_transformed = objWorld @ source[i].co
			else:
				co_transformed = source[i].co
			# Set locations and keyframes on a per-channel basis to allow for selective location changes
			if settings.vertex_location_x:
				targets[order[i]].location[0] = co_transformed[0]
				targets[order[i]].keyframe_insert(data_path="location", index = 0, frame=offsetFrame)
			if settings.vertex_location_y:
				targets[order[i]].location[1] = co_transformed[1]
				targets[order[i]].keyframe_insert(data_path="location", index = 1, frame=offsetFrame)
			if settings.vertex_location_z:
				targets[order[i]].location[2] = co_transformed[2]
				targets[order[i]].keyframe_insert(data_path="location", index = 2, frame=offsetFrame)
		
		return {'FINISHED'}



###########################################################################
# UI rendering class

class PRODUCTIONKIT_PT_vertexLocation(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'Launch'
	bl_order = 2
	bl_options = {'DEFAULT_CLOSED'}
	bl_label = "Vertex Location Keyframes"
	bl_idname = "PRODUCTIONKIT_PT_vertexLocation"
	
	@classmethod
	def poll(cls, context):
		return True
	
	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Vertex Location Keyframes panel header")
	
	def draw(self, context):
		settings = context.scene.production_kit_settings
		try:
			layout = self.layout
			layout.use_property_decorate = False # No animation
			
			row1 = layout.row()
			row1.prop(settings, 'vertex_location_x')
			row1.prop(settings, 'vertex_location_y')
			row1.prop(settings, 'vertex_location_z')
			
			row2 = layout.row()
			row2.prop(settings, 'vertex_location_world_space')
			row2.prop(settings, 'vertex_location_shuffle_order')
			row2.prop(settings, 'vertex_location_shuffle_timing')
			layout.prop(settings, 'vertex_location_keyframe_offset')
			
			box = layout.box()
			if context.view_layer.objects.active and context.view_layer.objects.active.type == "MESH":
				if len(context.view_layer.objects.selected) > 1:
					layout.operator(SetVertexLocationKeyframes.bl_idname)
					box.label(text=str(len(context.view_layer.objects.active.data.vertices)) + " vertices in source \"" + context.view_layer.objects.active.name + "\"")
					if context.view_layer.objects.active.select_get():
						box.label(text=str(len(context.view_layer.objects.selected) - 1) + " selected target items")
					else:
						box.label(text=str(len(context.view_layer.objects.selected)) + " selected target items")
				else:
					box.label(text="Select both source mesh and target objects")
			else:
				box.label(text="Active object must be a mesh")
		except Exception as exc:
			print(str(exc) + " | Error in Production Kit Vertex Location Keyframes panel")



###########################################################################
# Addon registration functions

classes = (SetVertexLocationKeyframes, PRODUCTIONKIT_PT_vertexLocation)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
