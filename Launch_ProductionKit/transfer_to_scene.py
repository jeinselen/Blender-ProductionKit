import bpy

# Operator to move, copy, or link collections or objects to a target scene
class OUTLINER_OT_transfer_to_scene(bpy.types.Operator):
	"""Move, copy, or link selected collections or objects to a target scene"""
	bl_idname = "outliner.transfer_to_scene"
	bl_label = "Transfer to Scene"
	bl_description = "Move, copy, or link selected collections or objects to a target scene"
	
	target_scene: bpy.props.StringProperty()
	
	transfer_mode: bpy.props.EnumProperty(
		name="Transfer Mode",
		description="How selected objects or collections should be added to the target scene",
		items=[
			('MOVE', "Move", "Move items to the target scene (default)"),
			('COPY', "Copy", "Duplicate copies to the target scene"),
			('LINK', "Link", "Link items to the target scene"),
		],
		default='MOVE',
	)
	
	@classmethod
	def poll(cls, context):
		return context.selected_ids is not None
	
	def execute(self, context):
		if not self.target_scene:
			self.report({'ERROR'}, "No target scene specified")
			return {'CANCELLED'}
		
		target_scene = bpy.data.scenes.get(self.target_scene)
		
		if not target_scene:
			self.report({'ERROR'}, f"Scene '{self.target_scene}' not found")
			return {'CANCELLED'}
		
		current_scene = context.scene
		
		if current_scene.name == target_scene.name:
			self.report({'WARNING'}, f"Target scene '{self.target_scene}' cannot be the active scene")
			return {'CANCELLED'}
		
		selected = context.selected_ids
		collections = [item for item in selected if isinstance(item, bpy.types.Collection)]
		objects = [item for item in selected if isinstance(item, bpy.types.Object)]
		
		if collections and objects:
			self.report({'INFO'}, "Mixed selection detected, only collections will be transferred")
		
		if collections:
			# Process only collections
			for coll in collections:
				if self.transfer_mode == 'MOVE':
					# Unlink and relink
					if coll.name in current_scene.collection.children and coll.name not in target_scene.collection.children:
						current_scene.collection.children.unlink(coll)
						target_scene.collection.children.link(coll)
					else:
						self.report({'WARNING'}, f"Collection '{coll.name}' may already exist in target scene '{self.target_scene}'")
				
				elif self.transfer_mode == 'COPY':
					# Duplicate and link
					new_coll = coll.copy()
					new_coll.name = coll.name + "_Copy"
					target_scene.collection.children.link(new_coll)
				
				elif self.transfer_mode == 'LINK':
					if coll.name not in target_scene.collection.children:
						target_scene.collection.children.link(coll)
		
		elif objects:
			# Process only objects
			for obj in objects:
				if self.transfer_mode == 'MOVE':
					# Unlink from all collections in the current scene
					for coll in current_scene.collection.children_recursive:
						if obj.name in coll.objects:
							print(f"Unlinking {obj.name} from {coll.name}")
							coll.objects.unlink(obj)
					
					# Also try to unlink from root collection (sometimes objects are directly in scene root)
					if obj.name in current_scene.collection.objects:
						current_scene.collection.objects.unlink(obj)
					
					# Link to the target scene's root collection
					if obj.name not in target_scene.collection.objects:
						print(f"Linking {obj.name} to {target_scene.name}")
						target_scene.collection.objects.link(obj)
					
					# Alternative approach:
#					for coll in obj.users_collection:
#						coll.objects.unlink(obj)
#					target_scene.collection.objects.link(obj)
				
				elif self.transfer_mode == 'COPY':
					new_obj = obj.copy()
					new_obj.data = obj.data.copy() if obj.data else None
					target_scene.collection.objects.link(new_obj)
					
				elif self.transfer_mode == 'LINK':
#					if obj.name not in target_scene.objects:
					if obj.name not in target_scene.collection.objects:
						target_scene.collection.objects.link(obj)
		
		else:
			self.report({'INFO'}, "No supported items selected (only collections or objects supported)")
			return {'CANCELLED'}
		
		return {'FINISHED'}



# Dynamic menus listing all but the current scene
class OUTLINER_MT_move_to_scene_menu(bpy.types.Menu):
	"""Submenu for Move to Scene options"""
	bl_label = "Move to Scene"
	bl_idname = "OUTLINER_MT_move_to_scene_menu"
	
	def draw(self, context):
		layout = self.layout
		current_scene = context.scene
		
		# Get all scenes except the current one
		other_scenes = [scene for scene in bpy.data.scenes if scene != current_scene]
		
		if not other_scenes:
			layout.label(text="No other scenes available")
			return
		
		# Add menu items for each scene
		for scene in other_scenes:
			op = layout.operator(
				OUTLINER_OT_transfer_to_scene.bl_idname,
				text=scene.name,
				icon='SCENE_DATA'
			)
			op.target_scene = scene.name
			op.transfer_mode = 'MOVE'



class OUTLINER_MT_copy_to_scene_menu(bpy.types.Menu):
	"""Submenu for Copy to Scene options"""
	bl_label = "Copy to Scene"
	bl_idname = "OUTLINER_MT_copy_to_scene_menu"
	
	def draw(self, context):
		layout = self.layout
		current_scene = context.scene
		
		# Get all scenes except the current one
		other_scenes = [scene for scene in bpy.data.scenes if scene != current_scene]
		
		if not other_scenes:
			layout.label(text="No other scenes available")
			return
		
		# Add menu items for each scene
		for scene in other_scenes:
			op = layout.operator(
				OUTLINER_OT_transfer_to_scene.bl_idname,
				text=scene.name,
				icon='SCENE_DATA'
			)
			op.target_scene = scene.name
			op.transfer_mode = 'COPY'



class OUTLINER_MT_link_to_scene_menu(bpy.types.Menu):
	"""Submenu for Link to Scene options"""
	bl_label = "Link to Scene"
	bl_idname = "OUTLINER_MT_link_to_scene_menu"
	
	def draw(self, context):
		layout = self.layout
		current_scene = context.scene
		
		# Get all scenes except the current one
		other_scenes = [scene for scene in bpy.data.scenes if scene != current_scene]
		
		if not other_scenes:
			layout.label(text="No other scenes available")
			return
		
		# Add menu items for each scene
		for scene in other_scenes:
			op = layout.operator(
				OUTLINER_OT_transfer_to_scene.bl_idname,
				text=scene.name,
				icon='SCENE_DATA'
			)
			op.target_scene = scene.name
			op.transfer_mode = 'LINK'



# Append the submenu to the Outliner context menu
def outliner_menu_draw(self, context):
	layout = self.layout
	layout.separator()
	layout.menu(OUTLINER_MT_move_to_scene_menu.bl_idname, icon='SCENE_DATA')
	layout.menu(OUTLINER_MT_copy_to_scene_menu.bl_idname, icon='DUPLICATE')
	layout.menu(OUTLINER_MT_link_to_scene_menu.bl_idname, icon='LINKED')



# Register/Unregister
classes = (
	OUTLINER_OT_transfer_to_scene,
	OUTLINER_MT_move_to_scene_menu,
	OUTLINER_MT_copy_to_scene_menu,
	OUTLINER_MT_link_to_scene_menu,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.OUTLINER_MT_asset.append(outliner_menu_draw)
#	bpy.types.OUTLINER_MT_object.append(outliner_menu_draw)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	bpy.types.OUTLINER_MT_asset.remove(outliner_menu_draw)
#	bpy.types.OUTLINER_MT_object.remove(outliner_menu_draw)

if __name__ == "__main__":
	register()