import bpy
import uuid
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories
from bpy.types import Context, Panel, Node, NodeTree, NodeSocket
from .options import skill_options


# ####TO-DO - condense drawing setflags and checkflags into a helper function

# Operator to toggle paramval on the flags, whatever that is
class ToggleParamvalOperator(bpy.types.Operator):
    bl_idname = "node.toggle_paramval"
    bl_label = "Toggle ParamVal"

    node_name: bpy.props.StringProperty()
    flag_index: bpy.props.IntProperty()

    def execute(self, context):
        # Get the node tree from the active node editor
        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "No active node editor found")
            return {'CANCELLED'}

        node_tree = space.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No active Dialogue node tree found")
            return {'CANCELLED'}

        node = node_tree.nodes.get(self.node_name)
        if not node:
            self.report({'ERROR'}, f"Node '{self.node_name}' not found")
            return {'CANCELLED'}

        flag = None
        if hasattr(node, "SetFlags"):
            flag = node.SetFlags[self.flag_index]
        elif hasattr(node, "CheckFlags"):
            flag = node.CheckFlags[self.flag_index]

        if flag:
            flag.has_paramval = not flag.has_paramval
            flag_id = getattr(flag, "name", "Some Flag")
            self.report({'INFO'}, f"Toggled ParamVal for flag {flag_id}")
        else:
            self.report({'ERROR'}, "Flag not found")

        return {'FINISHED'}

# A small extension for the Arrange Nodes addon to clear unnecessary duplicate links between nodes
class ArrangeAddonExtension(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Arrange"
    bl_label = "Dialogue Tools"
    bl_parent_id = "NA_PT_ArrangeSelected"  #Existing panel in the Arrange Nodes Addon

    def draw(self, context: Context):
        layout = self.layout
        layout.label(text="Dialogue Tools")
        layout.operator("node.remove_direct_links_bypassing_reroutes", text="Remove Redundant Connections")

# Custom socket for linking all types of Dialogue Nodes
class DialogueNodeSocket(bpy.types.NodeSocket):
    bl_idname = "DialogueNodeSocket"
    bl_label = "Dialogue Node Socket"
    def init(self, context):
        # Set link limit to allow unlimited connections
        self.link_limit = 0  # 0 means unlimited links

    def draw(self, context, layout, node, text):
        layout.label(text=self.name)

    def draw_color(self, context, node):
        return (0.5, 0.8, 1.0, 1.0)  # Light blue color for socket

    link_limit = 0  # 0 means unlimited links

    # A compatible socket type
    socket_type: bpy.props.StringProperty(name="Socket Type", default="Dialogue")
    
    
# ###### GLOBAL NODETREE PROPERTY GROUPS ######
class DefaultAddressedSpeakerItem(bpy.types.PropertyGroup):
    MapKey: bpy.props.IntProperty(name="MapKey", description="MapKey for addressed speaker", default=0)
    MapValue: bpy.props.IntProperty(name="MapValue", description="MapValue for addressed speaker", default=-1)

class SpeakerItem(bpy.types.PropertyGroup):
    index: bpy.props.StringProperty(name="Index", description="Index of the speaker")
    list: bpy.props.StringProperty(name="List", description="Speaker list entry")
    SpeakerMappingId: bpy.props.StringProperty(name="Mapping ID", description="Mapping ID of the speaker")

class ValidatedFlagsEntry(bpy.types.PropertyGroup):
    uuid: bpy.props.StringProperty(name="UUID", description="UUID of the node with ValidatedFlags")

    
# ###### NODETREE AND PROPERTIES ######
# Custom node tree for dialogue chains
class DialogueNodeTree(bpy.types.NodeTree):
    bl_idname = "DialogueNodeTree"
    bl_label = "Dialogue Node Tree"
    bl_icon = 'NODETREE'

    # Custom properties for global dialogue attributes, make the category Enum with other types later
    category: bpy.props.StringProperty(
        name="Category",
        description="Dialogue Category",
        default="Generic NPC Dialog"
    )
    UUID: bpy.props.StringProperty(
        name="UUID",
        description="UUID for the dialogue",
        default=""
    )
    TimelineId: bpy.props.StringProperty(
        name="Timeline ID",
        description="Timeline ID associated for the dialogue",
        default=""
    )

    # Collection for Default Addressed Speakers
    DefaultAddressedSpeakers: bpy.props.CollectionProperty(
        type=DefaultAddressedSpeakerItem,
        name="Default Addressed Speakers",
        description="Default Addressed Speaker"
    )

    # Collection for Speakers
    Speakers: bpy.props.CollectionProperty(
        type=SpeakerItem,
        name="Speakers",
        description="Speakers"
    )

    # To indicate whether it's a modified vanilla dialogue
    is_modification: bpy.props.BoolProperty(
        name="Is Modification",
        description="Check if the dialogue is a modification of an existing vanilla dialogue",
        default=False
    )

    validated_flags: bpy.props.CollectionProperty(type=ValidatedFlagsEntry)
    
# All the attributes under the TaggedText node
class TaggedTextItem(bpy.types.PropertyGroup):
    handle: bpy.props.StringProperty(name="Handle", description="Handle ID for the dialogue line")
    version: bpy.props.IntProperty(name="Version", description="Handle version", default=1)
    text: bpy.props.StringProperty(name="Text", description="Text for the dialogue line")
    has_tag_rule: bpy.props.BoolProperty(name="Has Tag Rule", default=True)
    stub: bpy.props.BoolProperty(name="Stub", default=True)
    lineid: bpy.props.StringProperty(name="Line ID", description="Line ID")


#For Nested Dialog Nodes (Speaker Linking Entries)
class SpeakerLinkingEntry(bpy.types.PropertyGroup):
    key: bpy.props.IntProperty(name="Key", description="Speaker Linking Entry Key")
    value: bpy.props.IntProperty(name="Value", description="Speaker Linking Entry Value")

# Checking and setting flags
class CheckFlagPropertyGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Flag Name", default="")
    is_true: bpy.props.BoolProperty(name="True", default=False)
    flag_type: bpy.props.EnumProperty(
        name="Flag Type",
        items=[
            ('Global', 'Global', 'Global Flag'),
            ('Local', 'Local', 'Local Flag'),
            ('Object', 'Object', 'Object Flag'),
            ('User', 'User', 'User Flag'),
            ('Tag', 'Tag', 'Tag Flag'),
            ('Dialog', 'Dialog', 'Dialog Flag'),
            ('Script', 'Script', 'Script Flag'),
            ('Quest', 'Quest', 'Quest Flag'),
        ],
        default='Global'
    )
    has_paramval: bpy.props.BoolProperty(name="Has ParamVal", description="Has ParamVal", default=False)
    paramval: bpy.props.IntProperty(name="ParamVal", description="Optional paramval for the flag", default=0)

    def toggle_paramval(self):
        self.has_paramval = not self.has_paramval

class SetFlagPropertyGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Flag Name", default="")
    is_true: bpy.props.BoolProperty(name="True", default=False)
    flag_type: bpy.props.EnumProperty(
        name="Flag Type",
        items=[
            ('Global', 'Global', 'Global Flag'),
            ('Local', 'Local', 'Local Flag'),
            ('Object', 'Object', 'Object Flag'),
            ('User', 'User', 'User Flag'),
            ('Tag', 'Tag', 'Tag Flag'),
            ('Dialog', 'Dialog', 'Dialog Flag'),
            ('Script', 'Script', 'Script Flag'),
            ('Quest', 'Quest', 'Quest Flag'),
        ],
        default='Global'
    )
    has_paramval: bpy.props.BoolProperty(name="Has ParamVal", description="Has ParamVal", default=False)
    paramval: bpy.props.IntProperty(name="ParamVal", description="Optional paramval for the flag", default=0)

    def toggle_paramval(self):
        self.has_paramval = not self.has_paramval
    
# DIALOGUE LINE NODE (Greeting, Answer, Question, Cinematic)
class DialogueLineNode(bpy.types.Node):
    bl_idname = "DialogueLineNode"
    bl_label = "Dialogue Line Node"

    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    # Cinematic Node Context property
    cinematic_node_context: bpy.props.StringProperty(
        name="Cinematic Node Context",
        default="",
        description="Notes for cinematic shots"
    )

    constructor_options = [
        ('TagGreeting', "TagGreeting", "Greeting dialogue line at the start"),
        ('TagAnswer', "TagAnswer", "Answer dialogue line"),
        ('TagQuestion', "TagQuestion", "Question dialogue line"),
        ('TagCinematic', "TagCinematic", "Cinematic shot"),
    ]

    constructor: bpy.props.EnumProperty(name="Constructor", items=constructor_options, default='TagGreeting')
    uuid: bpy.props.StringProperty(name="UUID")
    ShowOnce: bpy.props.BoolProperty(name="Show Once", default=False)
    groupid: bpy.props.StringProperty(name="Group ID", default="")
    groupindex: bpy.props.IntProperty(name="Group Index", default=0)
    root: bpy.props.BoolProperty(name="Root", default=False)
    endnode: bpy.props.BoolProperty(name="End Node", default=False)
    speaker: bpy.props.IntProperty(name="Speaker", default=0)
    approvalratingid: bpy.props.StringProperty(name="Approval Rating ID", default="")
    setflags: bpy.props.StringProperty(name="Set Flags", default="")
    checkflags: bpy.props.StringProperty(name="Check Flags", default="")
    
    handles_texts: bpy.props.CollectionProperty(
        type=TaggedTextItem,
        name="Handles and Texts",
        description="List of Handle-Text pairs and LineIDs"
    )
    
    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())
            
    def draw_buttons(self, context, layout):
        layout.prop(self, "constructor")
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "ShowOnce")
        layout.prop(self, "groupid")
        layout.prop(self, "groupindex")
        layout.prop(self, "root")
        layout.prop(self, "endnode")
        layout.prop(self, "speaker")
        layout.prop(self, "approvalratingid")
        for idx, item in enumerate(self.handles_texts):
            box = layout.box()
            box.prop(item, "has_tag_rule", text="Has Tag Rule")
            box.prop(item, "lineid", text="LineID")

            # Add Handle and Version in the same row
            row = box.row(align=True)
            row.prop(item, "handle", text="Handle")
            row.prop(item, "version", text="Version")

            # Add a button to generate a new handle
            generate_op = row.operator("node.generate_handle", text="New Handle")
            generate_op.index = idx
            generate_op.node_name = self.name
            generate_op.node_tree_name = self.id_data.name

            # Show text field for editing
            box.prop(item, "text", text="Text")

            # Add "Edit Text" button for full text expansion in a popup
            row = box.row(align=True)
            row.operator("node.edit_long_text", text="Edit Text").index = idx

            box.prop(item, "stub")
            
            remove_op = box.operator("node.remove_handle_text", text="Remove")
            remove_op.index = idx
            remove_op.node_name = self.name  # Pass the node's name here

        # Add button for adding a new handle-text pair
        add_op = layout.operator("node.add_handle_text", text="Add Handle and Text")
        add_op.node_name = self.name

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="UUID")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval in case has_paramval is True (find out what it does)
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")

            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="UUID")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")

            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

        # Editor Data section
        box = layout.box()
        box.label(text="Editor Data")
        box.prop(self, "cinematic_node_context", text="Cinematic Node Context")

    def draw_label(self):
        return f"Dialogue: {self.constructor}"
        

# JUMP NODE
class DialogueJumpNode(bpy.types.Node):
    bl_idname = "DialogueJumpNode"
    bl_label = "Dialogue Jump Node"

    uuid: bpy.props.StringProperty(name="UUID")
    jumptarget: bpy.props.StringProperty(name="Jump Target")
    jumptargetpoint: bpy.props.IntProperty(name="Jump Target Point", default=1)

    def init(self, context):
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    #Automatically update jumptarget based on node children
    def update(self):
        if self.outputs and self.outputs[0].is_linked:
            # Get the first connected node
            connected_node = self.outputs[0].links[0].to_node
            if connected_node and hasattr(connected_node, "uuid"):
                self.jumptarget = connected_node.uuid
            else:
                self.jumptarget = ""

    def draw_buttons(self, context, layout):
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "jumptarget")
        layout.prop(self, "jumptargetpoint")

    def draw_label(self):
        return "Jump Node"


# ROLL NODE (Active Roll, Passive Roll)
class DialogueRollNode(bpy.types.Node):
    bl_idname = "DialogueRollNode"
    bl_label = "Dialogue Roll Node"

    # Properties for SetFlags and CheckFlags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    ability_options = [
        ('Strength', "Strength", "Strength"),
        ('Dexterity', "Dexterity", "Dexterity"),
        ('Constitution', "Constitution", "Constitution"),
        ('Intelligence', "Intelligence", "Intelligence"),
        ('Wisdom', "Wisdom", "Wisdom"),
        ('Charisma', "Charisma", "Charisma"),
    ]

    Skill: bpy.props.EnumProperty(
        name="Skill",
        description="Select the skill associated with the Ability",
        items=skill_options,
        default='None'
    )

    Ability: bpy.props.EnumProperty(
        name="Ability",
        items=ability_options,
        default='Wisdom',
    )

    constructor_options = [
        ('ActiveRoll', "ActiveRoll", "Active roll"),
        ('PassiveRoll', "PassiveRoll", "Passive roll"),
    ]

    rolltype_options = [
        ('SkillCheck', "SkillCheck", "A skill check"),
        ('SavingThrow', "SavingThrow", "A saving throw"),
        ('RawAbility', "RawAbility", "A raw ability check"),
    ]

    DifficultyClassID_options = [
        # Act1
        ('4dfcb0ff-e02a-4efd-b132-77dfd956055e', 'Act1 Zero', 'DC 0'),
        ('2728289e-841d-4273-a29a-f24ae9f8c4fb', 'Act1 Negligible', 'DC 2'),
        ('8d398021-34e0-40b9-b7b2-0445f38a4c0b', 'Act1 Very Easy', 'DC 5'),
        ('31e92da6-bac9-46f7-af99-5f33d98fd4f0', 'Act1 Easy', 'DC 7'),
        ('fa621d38-6f83-4e42-a55c-6aa651a75d46', 'Act1 Medium', 'DC 10'),
        ('5e7ff0e9-6c80-459c-a636-3a3e8417a61a', 'Act1 Challenging', 'DC 12'),
        ('831e1fbe-428d-4f4d-bd17-4206d6efea35', 'Act1 Hard', 'DC 15'),
        ('8986db4d-09af-46ee-9781-ac88ec10fa0e', 'Act1 Very Hard', 'DC 18'),
        ('ea049218-36a8-4440-a3fc-f3019a57c86b', 'Act1 Nearly Impossible', 'DC 20'),
        # Act2
        ('9d1f2171-fef1-4c03-9e83-523485174c46', 'Act2 Very Easy', 'DC 6'),
        ('0d9484eb-f680-4a33-853d-46fda64883f2', 'Act2 Easy', 'DC 10'),
        ('89f0acd4-346f-479d-8b7a-1a3eb5382f6d', 'Act2 Medium', 'DC 14'),
        ('c44bfd7d-84de-4568-9c57-a059b8df5435', 'Act2 Challenging', 'DC 16'),
        ('91fb3598-dd68-4fa8-a306-2c7284709b08', 'Act2 Hard', 'DC 18'),
        ('f3aa825b-785e-4f4a-90af-565c7e943609', 'Act2 Very Hard', 'DC 21'),
        ('753ed8df-b5dc-4584-b9fa-de18c4c956b2', 'Act2 Extra Hard', 'DC 24'),
        ('52918812-bc1c-43b5-881a-58443902f5fa', 'Act2 Nearly Impossible', 'DC 30'),
        # Act3
        ('b9cea18d-f40a-444d-a692-76582a69130c', 'Act3 Very Easy', 'DC 7'),
        ('5028066b-6ea0-4a6a-9e3e-53bee62559a7', 'Act3 Easy', 'DC 10'),
        ('77cee1c4-384a-4217-b670-67db3c7add57', 'Act3 Medium', 'DC 15'),
        ('96bc76f2-0b2e-4a79-854f-e4971a772c36', 'Act3 Challenging', 'DC 18'),
        ('6298329e-255c-4826-9209-e911873b64e7', 'Act3 Hard', 'DC 20'),
        ('60916b01-ba4c-418e-9f30-19a669704b4d', 'Act3 Very Hard', 'DC 25'),
        ('7bf230a0-b68a-4c79-a785-79b498d6c36b', 'Act3 Nearly Impossible', 'DC 30'),
    ]

    constructor: bpy.props.EnumProperty(name="Constructor", items=constructor_options, default='ActiveRoll')
    uuid: bpy.props.StringProperty(name="UUID")
    ShowOnce: bpy.props.BoolProperty(name="Show Once", default=False)
    transitionmode: bpy.props.IntProperty(name="Transition Mode", default=0)
    speaker: bpy.props.IntProperty(name="Speaker", default=0)
    approvalratingid: bpy.props.StringProperty(name="Approval Rating ID", default="")
    RollType: bpy.props.EnumProperty(name="Roll Type", items=rolltype_options, default='SkillCheck')
    RollTargetSpeaker: bpy.props.IntProperty(name="Roll Target Speaker", default=0)
    Advantage: bpy.props.IntProperty(name="Advantage", default=0)
    ExcludeCompanionsOptionalBonuses: bpy.props.BoolProperty(name="Exclude Companions Optional Bonuses", default=False)
    ExcludeSpeakerOptionalBonuses: bpy.props.BoolProperty(name="Exclude Speaker Optional Bonuses", default=False)
    DifficultyClassID: bpy.props.EnumProperty(name="Difficulty Class", items=DifficultyClassID_options, default='31e92da6-bac9-46f7-af99-5f33d98fd4f0')
    setflags: bpy.props.StringProperty(name="Set Flags", default="")
    checkflags: bpy.props.StringProperty(name="Check Flags", default="")

    handles_texts: bpy.props.CollectionProperty(
        type=TaggedTextItem,
        name="Handles and Texts",
        description="List of Handle-Text pairs and LineIDs"
    )

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "constructor")
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "ShowOnce")
        layout.prop(self, "transitionmode")
        layout.prop(self, "speaker")
        layout.prop(self, "approvalratingid")
        layout.prop(self, "RollType")
        layout.prop(self, "Ability")
        layout.prop(self, "Skill")
        layout.prop(self, "RollTargetSpeaker")
        layout.prop(self, "Advantage")
        layout.prop(self, "ExcludeCompanionsOptionalBonuses")
        layout.prop(self, "ExcludeSpeakerOptionalBonuses")
        layout.prop(self, "DifficultyClassID")
        # Draw each Handle-Text pair in a box with buttons to remove
        for idx, item in enumerate(self.handles_texts):
            box = layout.box()
            box.prop(item, "has_tag_rule", text="Has Tag Rule")
            box.prop(item, "lineid", text="LineID")

            # Add Handle and Version in the same row
            row = box.row(align=True)
            row.prop(item, "handle", text="Handle")
            row.prop(item, "version", text="Version")

            # Add a button to generate a new handle
            generate_op = row.operator("node.generate_handle", text="New Handle")
            generate_op.index = idx
            generate_op.node_name = self.name
            generate_op.node_tree_name = self.id_data.name

            # Show text field for editing
            box.prop(item, "text", text="Text")

            # Add "Edit Text" button for full text expansion in a popup
            row = box.row(align=True)
            row.operator("node.edit_long_text", text="Edit Text").index = idx

            box.prop(item, "stub")
            
            remove_op = box.operator("node.remove_handle_text", text="Remove")
            remove_op.index = idx
            remove_op.node_name = self.name 

        # Add button for adding a new handle-text pair
        add_op = layout.operator("node.add_handle_text", text="Add Handle and Text")
        add_op.node_name = self.name

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

    def draw_label(self):
        return f"Dialogue: {self.constructor}"


# ROLL RESULT NODE
class DialogueRollResultNode(bpy.types.Node):
    bl_idname = "DialogueRollResultNode"
    bl_label = "Dialogue Roll Result Node"
    
    constructor: bpy.props.StringProperty(name="Constructor", default="RollResult")
    uuid: bpy.props.StringProperty(name="UUID")
    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    Success: bpy.props.BoolProperty(name="Success", default=False)

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "Success")

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval in the case has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval in the case has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

    def draw_label(self):
        return "Roll Result Node"


# DIALOGUE ALIAS NODE
class DialogueAliasNode(bpy.types.Node):
    bl_idname = "DialogueAliasNode"
    bl_label = "Dialogue Alias Node"

    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    constructor: bpy.props.StringProperty(name="Constructor", default="Alias")
    uuid: bpy.props.StringProperty(name="UUID")
    Greeting: bpy.props.BoolProperty(name="Greeting", default=False)
    root: bpy.props.BoolProperty(name="Root", default=False)
    endnode: bpy.props.BoolProperty(name="End Node", default=False)
    speaker: bpy.props.IntProperty(name="Speaker", default=0)
    sourcenode: bpy.props.StringProperty(name="Source Node", default="")
    setflags: bpy.props.StringProperty(name="Set Flags", default="")
    checkflags: bpy.props.StringProperty(name="Check Flags", default="")

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "constructor")
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "Greeting")
        layout.prop(self, "root")
        layout.prop(self, "endnode")
        layout.prop(self, "speaker")
        layout.prop(self, "sourcenode")
        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

    def draw_label(self):
        return f"Dialogue: {self.constructor}"


# VISUAL STATE NODE
class DialogueVisualStateNode(bpy.types.Node):
    bl_idname = "DialogueVisualStateNode"
    bl_label = "Dialogue Visual State Node"

    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    # Cinematic Node Context property
    cinematic_node_context: bpy.props.StringProperty(
        name="Cinematic Node Context",
        default="",
        description="Notes for cinematic shots"
    )

    constructor: bpy.props.StringProperty(name="Constructor", default="Visual State")
    uuid: bpy.props.StringProperty(name="UUID")
    groupid: bpy.props.StringProperty(name="Group ID", default="")
    groupindex: bpy.props.IntProperty(name="Group Index", default=0)
    setflags: bpy.props.StringProperty(name="Set Flags", default="")
    checkflags: bpy.props.StringProperty(name="Check Flags", default="")

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "constructor")
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "groupid")
        layout.prop(self, "groupindex")

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval in the case has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

        # Editor Data section
        box = layout.box()
        box.label(text="Editor Data")
        box.prop(self, "cinematic_node_context", text="Cinematic Node Context")

    def draw_label(self):
        return f"Dialogue: {self.constructor}"


# NESTED DIALOG NODE
class NestedDialogNode(bpy.types.Node):
    bl_idname = "NestedDialogNode"
    bl_label = "Nested Dialog Node"

    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)
    SpeakerLinkingEntry: bpy.props.CollectionProperty(type=SpeakerLinkingEntry)

    # Cinematic Node Context property
    cinematic_node_context: bpy.props.StringProperty(
        name="Cinematic Node Context",
        default="",
        description="Notes for cinematic shots"
    )

    constructor: bpy.props.StringProperty(name="Constructor", default="Nested Dialog")
    uuid: bpy.props.StringProperty(name="UUID")
    root: bpy.props.BoolProperty(name="Root", default=False)
    endnode: bpy.props.BoolProperty(name="End Node", default=False)
    NestedDialogNodeUUID: bpy.props.StringProperty(name="Nested Dialog Node UUID", default="")

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "NestedDialogNodeUUID", text="Nested Dialog Node UUID")
        layout.prop(self, "root")
        layout.prop(self, "endnode")

        # Draw Speaker Linking Entries
        box = layout.box()
        box.label(text="Speaker Linking Entries")
        for idx, entry in enumerate(self.SpeakerLinkingEntry):
            row = box.row(align=True)
            row.prop(entry, "key", text="Key")
            row.prop(entry, "value", text="Value")
            row.operator("node.remove_speaker_linking_entry", text="", icon="REMOVE").index = idx
        box.operator("node.add_speaker_linking_entry", text="", icon="ADD")

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

        # Editor Data section
        box = layout.box()
        box.label(text="Editor Data")
        box.prop(self, "cinematic_node_context", text="Cinematic Node Context")

    def draw_label(self):
        return "Nested Dialog Node"


# TRADE NODE
class TradeNode(bpy.types.Node):
    bl_idname = "TradeNode"
    bl_label = "Trade Node"

    # Properties for flags
    SetFlags: bpy.props.CollectionProperty(type=SetFlagPropertyGroup)
    CheckFlags: bpy.props.CollectionProperty(type=CheckFlagPropertyGroup)

    constructor: bpy.props.StringProperty(name="Constructor", default="Trade")
    uuid: bpy.props.StringProperty(name="UUID")
    speaker: bpy.props.IntProperty(name="Speaker", default=0)
    trademode: bpy.props.IntProperty(name="Trade Mode", default=1)

    def init(self, context):
        self.width = 400
        # Use the custom socket class for inputs and outputs
        input_socket = self.inputs.new('DialogueNodeSocket', "Input")
        input_socket.link_limit = 0  # Unlimited links

        output_socket = self.outputs.new('DialogueNodeSocket', "Output")
        output_socket.link_limit = 0  # Unlimited links
        if not self.get("uuid"):
            self["uuid"] = str(uuid.uuid4())

    def draw_buttons(self, context, layout):
        layout.prop(self, "uuid", text="UUID")
        layout.prop(self, "speaker")
        layout.prop(self, "trademode")

        # SetFlags section
        box = layout.box()
        box.label(text="Set Flags")
        for i, flag in enumerate(self.SetFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_setflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_setflag", text="", icon='ADD').node_name = self.name

        # CheckFlags section
        box = layout.box()
        box.label(text="Check Flags")
        for i, flag in enumerate(self.CheckFlags):
            row = box.row(align=True)
            row.prop(flag, "name", text="")
            row.prop(flag, "is_true", text="True")
            row.prop(flag, "flag_type", text="Type")
            toggle_op = row.operator("node.toggle_paramval",
                                     text="+ ParamVal" if not flag.has_paramval else "- ParamVal")
            toggle_op.node_name = self.name
            toggle_op.flag_index = i

            # Show paramval given has_paramval is True
            if flag.has_paramval:
                row.prop(flag, "paramval", text="ParamVal")
            row.operator("node.remove_checkflag", text="", icon='REMOVE').node_name = self.name
        box.operator("node.add_checkflag", text="", icon='ADD').node_name = self.name

        # Editor Data section
        box = layout.box()
        box.label(text="Editor Data")
    def draw_label(self):
        return "Trade Node"

# ###### CUSTOM NODE CATEGORY FOR THE ADD MENU ######
class DialogueChainNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'DialogueNodeTree'

# Register node categories for the Add Menu
node_categories = [
    DialogueChainNodeCategory('DIALOGUE_CHAIN_NODES', "Dialogue Chain Nodes", items=[
        NodeItem('DialogueLineNode'),
        NodeItem('DialogueJumpNode'),
        NodeItem('DialogueRollNode'),
        NodeItem('DialogueRollResultNode'),
        NodeItem('DialogueAliasNode'),
        NodeItem('DialogueVisualStateNode'),
        NodeItem('NestedDialogNode'),
        NodeItem('TradeNode'),
    ]),
]


# Register and unregister nodes
def register():
    bpy.utils.register_class(ArrangeAddonExtension)
    bpy.utils.register_class(DefaultAddressedSpeakerItem)
    bpy.utils.register_class(SpeakerItem)
    bpy.utils.register_class(TaggedTextItem)
    bpy.utils.register_class(ValidatedFlagsEntry)
    bpy.utils.register_class(SpeakerLinkingEntry)
    bpy.utils.register_class(CheckFlagPropertyGroup)
    bpy.utils.register_class(SetFlagPropertyGroup)
    bpy.utils.register_class(ToggleParamvalOperator)
    bpy.utils.register_class(DialogueNodeSocket)
    bpy.utils.register_class(DialogueNodeTree)
    bpy.utils.register_class(DialogueLineNode)
    bpy.utils.register_class(DialogueJumpNode)
    bpy.utils.register_class(DialogueRollNode)
    bpy.utils.register_class(DialogueRollResultNode)
    bpy.utils.register_class(DialogueAliasNode)
    bpy.utils.register_class(DialogueVisualStateNode)
    bpy.utils.register_class(NestedDialogNode)
    bpy.utils.register_class(TradeNode)
    register_node_categories('DIALOGUE_CHAIN_NODES', node_categories)


def unregister():
    bpy.utils.unregister_class(ArrangeAddonExtension)
    bpy.utils.unregister_class(DefaultAddressedSpeakerItem)
    bpy.utils.unregister_class(SpeakerItem)
    bpy.utils.unregister_class(TaggedTextItem)
    bpy.utils.unregister_class(ValidatedFlagsEntry)
    bpy.utils.unregister_class(SpeakerLinkingEntry)
    bpy.utils.unregister_class(CheckFlagPropertyGroup)
    bpy.utils.unregister_class(SetFlagPropertyGroup)
    bpy.utils.unregister_class(ToggleParamvalOperator)
    unregister_node_categories('DIALOGUE_CHAIN_NODES')
    bpy.utils.unregister_class(DialogueJumpNode)
    bpy.utils.unregister_class(DialogueRollNode)
    bpy.utils.unregister_class(DialogueLineNode)
    bpy.utils.unregister_class(DialogueRollResultNode)
    bpy.utils.unregister_class(DialogueAliasNode)
    bpy.utils.unregister_class(DialogueVisualStateNode)
    bpy.utils.unregister_class(NestedDialogNode)
    bpy.utils.unregister_class(TradeNode)
    bpy.utils.unregister_class(DialogueNodeTree)
    bpy.utils.unregister_class(DialogueNodeSocket)
