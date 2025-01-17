bl_info = {
    "name": "BG3 Dialogue Chain Node Editor",
    "author": "kirixiar",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Shader Editor > Sidebar",
    "description": "Use Blender's Node Editor for BG3 dialogue chains in DialogsBinary lsf files.",
    "category": "Node",
}

import bpy

from .nodes import DialogueNodeTree

# Config for localisation xml file path (extracted with lslib or the multitool)
class DialogueAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    localisation_path: bpy.props.StringProperty(
        name="BG3 Localisation File Path",
        description="Path to the main BG3 localisation XML file",
        default="",
        subtype='FILE_PATH'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "localisation_path")

# Panel in the node tree editor to interact with dialogue features and display global dialogue attributes e.g. timelineid
class DialogueNodePanel(bpy.types.Panel):
    bl_label = "Dialogue Chain Editor"
    bl_idname = "NODE_PT_dialogue_chain"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Dialogue"

    def draw(self, context):
        layout = self.layout
        # Get the active node tree
        node_tree = context.space_data.edit_tree
        if not isinstance(node_tree, DialogueNodeTree):
            layout.label(text="No active Dialogue Node Tree")
            return

        layout.operator("node.new_dialogue_tree", text="New Dialogue Tree")
        layout.operator("node.import_dialogue_xml", text="Import Dialogue XML")
        layout.operator("node.export_dialogue_xml", text="Export Dialogue XML")
        layout.prop(node_tree, "is_modification", text="Is Modification")
        layout.operator("node.export_localisation", text="Export Localisation")
        # Input field for UUID
        layout.prop(context.scene, "zoom_to_uuid", text="UUID")
        # Operator to snap the view to uuid input
        layout.operator(ZoomToNodeOperator.bl_idname, text="Snap View to Node by UUID")

        # Display global attributes
        layout.prop(node_tree, "category", text="Category")
        layout.prop(node_tree, "UUID", text="UUID")
        layout.prop(node_tree, "TimelineId", text="Timeline ID")

        # Display Default Addressed Speakers
        layout.label(text="Default Addressed Speakers:")
        for idx, speaker in enumerate(node_tree.DefaultAddressedSpeakers):
            box = layout.box()
            box.prop(speaker, "MapKey", text="MapKey")
            box.prop(speaker, "MapValue", text="MapValue")
            remove_op = box.operator("node.remove_default_speaker", text="Remove Default Speakers")
            remove_op.index = idx

        # Add an option to add a new speaker
        layout.operator("node.add_default_speaker", text="Add Default Speakers")

        # Display Speakers
        layout.label(text="Speakers:")
        for idx, speaker in enumerate(node_tree.Speakers):
            box = layout.box()
            box.prop(speaker, "index", text="Index")
            box.prop(speaker, "list", text="List")
            box.prop(speaker, "SpeakerMappingId", text="Mapping ID")
            remove_op = box.operator("node.remove_speaker", text="Remove Speaker")
            remove_op.index = idx

        # Add an option to add a new speaker
        layout.operator("node.add_speaker", text="+ New Speaker")


# Operator to zoom/select and center into the node by UUID
class ZoomToNodeOperator(bpy.types.Operator):
    """Zoom to Node by UUID"""
    bl_idname = "node.zoom_to_node_by_uuid"
    bl_label = "Zoom to Node by UUID"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not context.space_data or context.space_data.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Not in a Node Editor")
            return {'CANCELLED'}
        node_tree = context.space_data.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}
        # Get the UUID from the custom property
        uuid = context.scene.zoom_to_uuid
        if not uuid:
            self.report({'ERROR'}, "UUID is empty")
            return {'CANCELLED'}

        # Find the node with the specified UUID
        target_node = None
        for node in node_tree.nodes:
            if getattr(node, "uuid", None) == uuid:
                target_node = node
                break

        if not target_node:
            self.report({'ERROR'}, f"Node with UUID {uuid} not found")
            return {'CANCELLED'} # if the node with the specified UUID is not found in the nodetree

        # Deselect all nodes and select the target node
        for node in node_tree.nodes:
            node.select = False  # Deselect all nodes just in case
        target_node.select = True
        node_tree.nodes.active = target_node

        # Ensure the correct area is active
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        # Override the context
                        with bpy.context.temp_override(area=area, region=region):
                            try:
                                bpy.ops.node.view_selected()
                            except RuntimeError as e:
                                self.report({'ERROR'}, f"Failed to snap view: {e}")
                                return {'CANCELLED'}
                break

        self.report({'INFO'}, f"Snapped view to node {target_node.name}")
        return {'FINISHED'}

def register():
    from . import import_operators
    from . import nodes
    from . import export_operators
    bpy.types.Scene.zoom_to_uuid = bpy.props.StringProperty(
        name="Zoom To UUID",
        description="UUID of the node to zoom to",
        default="")
    bpy.utils.register_class(DialogueAddonPreferences)
    bpy.utils.register_class(DialogueNodePanel)
    bpy.utils.register_class(ZoomToNodeOperator)
    import_operators.register()
    export_operators.register()
    nodes.register()

def unregister():
    from . import import_operators
    from . import nodes
    from . import export_operators
    del bpy.types.Scene.zoom_to_uuid
    bpy.utils.unregister_class(DialogueAddonPreferences)
    bpy.utils.unregister_class(DialogueNodePanel)
    bpy.utils.unregister_class(ZoomToNodeOperator)
    import_operators.unregister()
    export_operators.unregister()
    nodes.unregister()

if __name__ == '__main__':
    register()
