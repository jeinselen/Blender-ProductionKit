import bpy
from mathutils import Vector, Euler

###########################################################################
# Main class

class OBJECT_OT_shift_transforms(bpy.types.Operator):
	"""Shift transforms of selected objects"""
	bl_idname = "object.shift_transforms"
	bl_label = "Shift Item Transforms"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		return (context.mode == 'OBJECT' and len(context.selected_objects) >= 2)
	
	def execute(self, context):
		selected_objects = context.selected_objects
		
		if len(selected_objects) < 2:
			self.report({'WARNING'}, "At least 2 objects must be selected")
			return {'CANCELLED'}
		
		# Store transforms
		transforms = []
		for obj in selected_objects:
			transforms.append({
				'location': obj.location.copy(),
				'rotation_euler': obj.rotation_euler.copy(),
				'scale': obj.scale.copy()
			})
		
		# Shift transforms by one position (wrap around)
		shifted_transforms = [transforms[-1]] + transforms[:-1]
		
		# Apply shifted transforms
		for obj, transform in zip(selected_objects, shifted_transforms):
			obj.location = transform['location']
			obj.rotation_euler = transform['rotation_euler']
			obj.scale = transform['scale']
		
		# Update the scene
		context.view_layer.update()
		
		self.report({'INFO'}, f"Shifted transforms for {len(selected_objects)} objects")
		return {'FINISHED'}

###########################################################################
# Menu UI

def menu_func(self, context):
	# Only show menu item if 2 or more objects are selected
	if len(context.selected_objects) >= 2:
		self.layout.operator(OBJECT_OT_shift_transforms.bl_idname)

def register():
	bpy.utils.register_class(OBJECT_OT_shift_transforms)
	bpy.types.VIEW3D_MT_transform_object.append(menu_func)

def unregister():
	bpy.utils.unregister_class(OBJECT_OT_shift_transforms)
	bpy.types.VIEW3D_MT_transform_object.remove(menu_func)

if __name__ == "__main__":
	register()