import os
import xml.etree.ElementTree as ET

import bpy

from .nodes import (DialogueNodeTree, DialogueJumpNode,
                    NestedDialogNode, DialogueLineNode, DialogueRollNode, DialogueRollResultNode,
                    DialogueAliasNode, DialogueVisualStateNode, TradeNode)


def indent_tree(elem, level=0):
   # Properly indent the exported xml for readability
    i = "\n" + "    " * level  # Current level indentation

    # Indent the element's text for its first child
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent_tree(child, level + 1)
        # Align the closing tag of the current element
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        # Align closing tag for elements without children
        if not elem.text or not elem.text.strip():
            elem.text = None
        if not elem.tail or not elem.tail.strip():
            elem.tail = i

    # Ensure correct indentation for attributes or direct siblings
    prev = None
    for subelem in list(elem):
        if prev is not None and (not prev.tail or not prev.tail.strip()):
            prev.tail = i + "    "
        prev = subelem

    # Align the closing tag of the parent element
    if level > 0 and (not elem.tail or not elem.tail.strip()):
        elem.tail = "\n" + "    " * (level - 1)

# HELPER FUNCTIONS FOR WRITING TO XML
def add_attribute(xml_node, attr_id, attr_type, attr_value):
    ET.SubElement(xml_node, "attribute", {"id": attr_id, "type": attr_type, "value": str(attr_value)})

def add_child_node(xml_node, child_id, child_key=None):
    attributes = {"id": child_id}
    if child_key:
        attributes["key"] = child_key
    return ET.SubElement(xml_node, "node", attributes)


def process_editor_data(xml_parent, dialogue_node):
    if hasattr(dialogue_node, "cinematic_node_context") and dialogue_node.cinematic_node_context:
        # Create the editorData node
        editor_data_node = ET.SubElement(xml_parent, "node", {"id": "editorData"})

        # Add data node for CinematicNodeContext
        data_node = ET.SubElement(editor_data_node, "node", {"id": "data"})
        ET.SubElement(data_node, "attribute", {"id": "key", "type": "FixedString", "value": "CinematicNodeContext"})
        ET.SubElement(data_node, "attribute",
                      {"id": "val", "type": "FixedString", "value": dialogue_node.cinematic_node_context})


def export_flags(xml_node, flags, flag_type):
    if flags:
        flag_section = ET.SubElement(xml_node, "node", {"id": flag_type})
        flag_children = ET.SubElement(flag_section, "children")
        for flag in flags:
            flaggroup = ET.SubElement(flag_children, "node", {"id": "flaggroup", "key": "type"})
            add_attribute(flaggroup, "type", "FixedString", flag.flag_type)
            flag_group_children = ET.SubElement(flaggroup, "children")
            flag_node = ET.SubElement(flag_group_children, "node", {"id": "flag"})
            ET.SubElement(flag_node, "attribute", {"id": "UUID", "type": "FixedString", "value": flag.name})
            ET.SubElement(flag_node, "attribute", {"id": "value", "type": "bool", "value": str(flag.is_true).lower()})
            if flag.has_paramval:
                ET.SubElement(flag_node, "attribute", {"id": "paramval", "type": "int32", "value": str(flag.paramval)})
    else:
        # Add an empty node still if no flags are provided
        ET.SubElement(xml_node, "node", {"id": flag_type})

def export_speaker_linking_entries(xml_node, speaker_links):
    if speaker_links:
        speaker_section = ET.SubElement(xml_node, "node", {"id": "SpeakerLinking"})
        for link in speaker_links:
            link_node = ET.SubElement(speaker_section, "node", {"id": "SpeakerLinkingEntry"})
            ET.SubElement(link_node, "attribute", {"id": "Key", "type": "int32", "value": str(link.key)})
            ET.SubElement(link_node, "attribute", {"id": "Value", "type": "int32", "value": str(link.value)})
    else:
        # Add an empty SpeakerLinking node even if there are no entries just in case
        ET.SubElement(xml_node, "node", {"id": "SpeakerLinking"})


# Add handles and texts for dialogue nodes
def export_handles_and_texts(children_section, dialogue_node):
    handles_texts_node = ET.SubElement(children_section, "node", {"id": "TaggedTexts"})
    handles_texts_children = ET.SubElement(handles_texts_node, "children")

    for handle_text in dialogue_node.handles_texts:
        tagged_text_node = ET.SubElement(handles_texts_children, "node", {"id": "TaggedText"})
        ET.SubElement(tagged_text_node, "attribute", {
            "id": "HasTagRule", "type": "bool", "value": "True" if handle_text.has_tag_rule else "False"
        })

        tagged_text_children = ET.SubElement(tagged_text_node, "children")
        tag_texts_node = ET.SubElement(tagged_text_children, "node", {"id": "TagTexts"})
        tag_texts_children = ET.SubElement(tag_texts_node, "children")

        tag_text_node = ET.SubElement(tag_texts_children, "node", {"id": "TagText"})
        ET.SubElement(tag_text_node, "attribute", {
            "id": "TagText",
            "type": "TranslatedString",
            "handle": handle_text.handle,
            "version": str(handle_text.version)
        })
        ET.SubElement(tag_text_node, "attribute", {
            "id": "LineId", "type": "guid", "value": handle_text.lineid
        })
        ET.SubElement(tag_text_node, "attribute", {
            "id": "stub", "type": "bool", "value": "True" if handle_text.stub else "False"
        })

        # Add RuleGroup section
        rule_group_node = ET.SubElement(tagged_text_children, "node", {"id": "RuleGroup"})
        ET.SubElement(rule_group_node, "attribute", {"id": "TagCombineOp", "type": "uint8", "value": "0"})
        rule_group_children = ET.SubElement(rule_group_node, "children")

        # Add empty Rules node - expand on this assuming there are some rules used somewhere
        ET.SubElement(rule_group_children, "node", {"id": "Rules"})

#Helper functions to get child nodes from Blender nodetree connections
def get_child_nodes(node):
    child_nodes = []
    for output in node.outputs:
        for link in output.links:
            connected_node = link.to_node
            # Skip reroute nodes if there are any and go to the next connected node
            while connected_node and connected_node.bl_idname == 'NodeReroute':
                # Follow the output of the reroute node
                if connected_node.outputs and connected_node.outputs[0].links:
                    connected_node = connected_node.outputs[0].links[0].to_node
                else:
                    connected_node = None
            if connected_node and connected_node not in child_nodes:
                child_nodes.append(connected_node)
    return child_nodes

def export_child_connections(xml_node, node_tree, parent_node):
    child_nodes = get_child_nodes(parent_node)
    if child_nodes:
        child_nodes_section = ET.SubElement(xml_node, "node", {"id": "children"})
        child_nodes_children = ET.SubElement(child_nodes_section, "children")
        for connected_node in child_nodes:
            child_node = add_child_node(child_nodes_children, "child")
            add_attribute(child_node, "UUID", "FixedString", connected_node.uuid)
    else:
        # Add an empty <node id="children" /> tag if no child nodes exist
        ET.SubElement(xml_node, "node", {"id": "children"})


# ######FUNCTIONS FOR EACH NODE CONSTRUCTOR TYPE EXPORT######
def add_jump_node(xml_parent, jump_node, node_tree):
    node = ET.SubElement(xml_parent, "node", {"id": "node", "key": "UUID"})
    ET.SubElement(node, "attribute", {"id": "constructor", "type": "FixedString", "value": "Jump"})
    ET.SubElement(node, "attribute", {"id": "UUID", "type": "FixedString", "value": jump_node.uuid})
    ET.SubElement(node, "attribute", {"id": "jumptarget", "type": "FixedString", "value": jump_node.jumptarget})
    # Convert jumptargetpoint to string and add to XML
    jumptargetpoint = getattr(jump_node, "jumptargetpoint", 1)
    ET.SubElement(node, "attribute", {"id": "jumptargetpoint", "type": "uint8", "value": str(jumptargetpoint)})

    # Add children nodes
    children_section = ET.SubElement(node, "children")

    # Always close these sections immediately as a jump node is not really supposed to have them
    ET.SubElement(children_section, "node", {"id": "children"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    ET.SubElement(children_section, "node", {"id": "setflags"})
    ET.SubElement(children_section, "node", {"id": "checkflags"})

def add_dialogue_line_node(xml_parent, dialogue_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", dialogue_node.constructor)
    add_attribute(node, "UUID", "FixedString", dialogue_node.uuid)
    # Conditionally add attributes if they exist/are true
    if dialogue_node.groupid:
        add_attribute(node, "GroupID", "FixedString", dialogue_node.groupid)
        add_attribute(node, "GroupIndex", "int32", dialogue_node.groupindex)
    if dialogue_node.root:
        add_attribute(node, "Root", "bool", dialogue_node.root)
    add_attribute(node, "speaker", "int32", dialogue_node.speaker)
    if dialogue_node.ShowOnce:
        add_attribute(node, "ShowOnce", "bool", dialogue_node.ShowOnce)
    if dialogue_node.endnode:
        add_attribute(node, "endnode", "bool", dialogue_node.endnode)

    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, dialogue_node)
    # Add GameData section and CinematicNodeContext
    game_data_node = ET.SubElement(children_section, "node", {"id": "GameData"})
    game_data_children = ET.SubElement(game_data_node, "children")
    ET.SubElement(game_data_children, "node", {"id": "AiPersonalities", "key": "AiPersonality"})
    ET.SubElement(game_data_children, "node", {"id": "MusicInstrumentSounds"})
    ET.SubElement(game_data_children, "node", {"id": "OriginSound"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    process_editor_data(xml_parent, dialogue_node)

    # Add flags and handles/texts
    export_flags(children_section, dialogue_node.SetFlags, "setflags")
    export_flags(children_section, dialogue_node.CheckFlags, "checkflags")
    export_handles_and_texts(children_section, dialogue_node)

    # Add ValidatedFlags section if applicable (whatever that does)
    export_validated_flags(children_section, dialogue_node)

def export_validated_flags(xml_parent, dialogue_node):
    if any(entry.uuid == dialogue_node.uuid for entry in dialogue_node.id_data.validated_flags):
        validated_flags_node = ET.SubElement(xml_parent, "node", {"id": "ValidatedFlags"})
        ET.SubElement(validated_flags_node, "attribute", {"id": "ValidatedHasValue", "type": "bool", "value": "False"})

def add_roll_node(xml_parent, roll_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", roll_node.constructor)
    add_attribute(node, "UUID", "FixedString", roll_node.uuid)
    # Conditionally add attributes if they exist/are true
    if roll_node.ShowOnce:
        add_attribute(node, "GroupID", "bool", roll_node.ShowOnce)
    add_attribute(node, "transitionmode", "uint8", roll_node.transitionmode)
    add_attribute(node, "speaker", "int32", roll_node.speaker)
    add_attribute(node, "approvalratingid", "guid", roll_node.approvalratingid)
    add_attribute(node, "RollType", "string", roll_node.RollType)
    add_attribute(node, "Ability", "string", roll_node.Ability)
    add_attribute(node, "Skill", "string", roll_node.Skill)
    add_attribute(node, "RollTargetSpeaker", "int32", roll_node.RollTargetSpeaker)
    add_attribute(node, "Advantage", "uint8", roll_node.Advantage)
    add_attribute(node, "ExcludeCompanionsOptionalBonuses", "bool", roll_node.ExcludeCompanionsOptionalBonuses)
    add_attribute(node, "ExcludeSpeakerOptionalBonuses", "bool", roll_node.ExcludeSpeakerOptionalBonuses)
    add_attribute(node, "DifficultyClassID", "guid", roll_node.DifficultyClassID)

    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, roll_node)
    # Add GameData section and CinematicNodeContext
    game_data_node = ET.SubElement(children_section, "node", {"id": "GameData"})
    game_data_children = ET.SubElement(game_data_node, "children")
    ET.SubElement(game_data_children, "node", {"id": "AiPersonalities", "key": "AiPersonality"})
    ET.SubElement(game_data_children, "node", {"id": "MusicInstrumentSounds"})
    ET.SubElement(game_data_children, "node", {"id": "OriginSound"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    process_editor_data(xml_parent, roll_node)

    # Add flags and handles/texts
    export_flags(children_section, roll_node.SetFlags, "setflags")
    export_flags(children_section, roll_node.CheckFlags, "checkflags")
    export_handles_and_texts(children_section, roll_node)

    # Add ValidatedFlags section
    export_validated_flags(children_section, roll_node)

def add_rollresult_node(xml_parent, rollresult_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", rollresult_node.constructor)
    add_attribute(node, "UUID", "FixedString", rollresult_node.uuid)
    add_attribute(node, "Success", "bool", rollresult_node.Success)
    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, rollresult_node)

    ET.SubElement(children_section, "node", {"id": "Tags"})
    # Add flags
    export_flags(children_section, rollresult_node.SetFlags, "setflags")
    export_flags(children_section, rollresult_node.CheckFlags, "checkflags")
    # Add ValidatedFlags section
    export_validated_flags(children_section, rollresult_node)

def add_alias_node(xml_parent, alias_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", alias_node.constructor)
    add_attribute(node, "UUID", "FixedString", alias_node.uuid)
    # Conditionally add attributes if they exist/are true
    if alias_node.Greeting:
        add_attribute(node, "Greeting", "bool", alias_node.Greeting)
    if alias_node.root:
        add_attribute(node, "Root", "bool", alias_node.root)
    add_attribute(node, "speaker", "int32", alias_node.speaker)
    if alias_node.endnode:
        add_attribute(node, "endnode", "bool", alias_node.endnode)

    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, alias_node)
    # Add GameData section and CinematicNodeContext
    game_data_node = ET.SubElement(children_section, "node", {"id": "GameData"})
    game_data_children = ET.SubElement(game_data_node, "children")
    ET.SubElement(game_data_children, "node", {"id": "AiPersonalities", "key": "AiPersonality"})
    ET.SubElement(game_data_children, "node", {"id": "MusicInstrumentSounds"})
    ET.SubElement(game_data_children, "node", {"id": "OriginSound"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    process_editor_data(xml_parent, alias_node)

    # Add flags and handles/texts
    export_flags(children_section, alias_node.SetFlags, "setflags")
    export_flags(children_section, alias_node.CheckFlags, "checkflags")

    # Add ValidatedFlags section
    export_validated_flags(children_section, alias_node)

def add_visualstate_node(xml_parent, visualstate_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", visualstate_node.constructor)
    add_attribute(node, "UUID", "FixedString", visualstate_node.uuid)
    # Conditionally add attributes if they exist/are true
    if visualstate_node.groupid:
        add_attribute(node, "GroupID", "FixedString", visualstate_node.groupid)
        add_attribute(node, "GroupIndex", "int32", visualstate_node.groupindex)
    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, visualstate_node)
    # Add GameData section
    game_data_node = ET.SubElement(children_section, "node", {"id": "GameData"})
    game_data_children = ET.SubElement(game_data_node, "children")
    ET.SubElement(game_data_children, "node", {"id": "AiPersonalities", "key": "AiPersonality"})
    ET.SubElement(game_data_children, "node", {"id": "MusicInstrumentSounds"})
    ET.SubElement(game_data_children, "node", {"id": "OriginSound"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    # Add flags and handles/texts
    export_flags(children_section, visualstate_node.SetFlags, "setflags")
    export_flags(children_section, visualstate_node.CheckFlags, "checkflags")
    # Add ValidatedFlags section
    export_validated_flags(children_section, visualstate_node)

def add_nesteddialog_node(xml_parent, nesteddialog_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", nesteddialog_node.constructor)
    add_attribute(node, "UUID", "FixedString", nesteddialog_node.uuid)
    # Conditionally add attributes if they exist/are true
    if nesteddialog_node.root:
        add_attribute(node, "Root", "bool", nesteddialog_node.root)
    if nesteddialog_node.endnode:
        add_attribute(node, "endnode", "bool", nesteddialog_node.endnode)
    add_attribute(node, "NestedDialogNodeUUID", "guid", nesteddialog_node.NestedDialogNodeUUID)

    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, nesteddialog_node)
    ET.SubElement(children_section, "node", {"id": "Tags"})
    # Add flags and speaker linking entries for the related nested dialogue
    export_flags(children_section, nesteddialog_node.SetFlags, "setflags")
    export_flags(children_section, nesteddialog_node.CheckFlags, "checkflags")
    export_speaker_linking_entries(children_section, nesteddialog_node.SpeakerLinkingEntry)
    # Add ValidatedFlags section
    export_validated_flags(children_section, nesteddialog_node)

def add_trade_node(xml_parent, trade_node, node_tree):
    node = add_child_node(xml_parent, "node", "UUID")
    add_attribute(node, "constructor", "FixedString", trade_node.constructor)
    add_attribute(node, "UUID", "FixedString", trade_node.uuid)
    add_attribute(node, "speaker", "int32", trade_node.speaker)
    add_attribute(node, "trademode", "uint8", trade_node.trademode)
    # Add children
    children_section = ET.SubElement(node, "children")
    export_child_connections(children_section, node_tree, trade_node)
    # Add GameData section
    game_data_node = ET.SubElement(children_section, "node", {"id": "GameData"})
    game_data_children = ET.SubElement(game_data_node, "children")
    ET.SubElement(game_data_children, "node", {"id": "AiPersonalities", "key": "AiPersonality"})
    ET.SubElement(game_data_children, "node", {"id": "MusicInstrumentSounds"})
    ET.SubElement(game_data_children, "node", {"id": "OriginSound"})
    ET.SubElement(children_section, "node", {"id": "Tags"})
    process_editor_data(xml_parent, trade_node)
    # Add flags and handles/texts
    export_flags(children_section, trade_node.SetFlags, "setflags")
    export_flags(children_section, trade_node.CheckFlags, "checkflags")
    # Add ValidatedFlags section
    export_validated_flags(children_section, trade_node)

class ExportDialogueXML(bpy.types.Operator):
    bl_idname = "node.export_dialogue_xml"
    bl_label = "Export Dialogue XML"
    bl_description = "Export dialogue nodes to an XML file"
    filename_ext = ".xml"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        node_tree = context.space_data.node_tree
        if not node_tree or node_tree.bl_idname != "DialogueNodeTree":
            self.report({'ERROR'}, "No active DialogueNodeTree found. You should be in a DialogueNodeTree.")
            return {'CANCELLED'}

        try:
            self.add_global_root(node_tree, self.filepath)
            self.report({'INFO'}, f"Dialogue XML exported to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export XML: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    #Global attributes for every DialogsBinary
    def add_global_root(self, node_tree, filepath):
        root = ET.Element("save")
        region = ET.SubElement(root, "region", {"id": "dialog"})
        dialog_node = ET.SubElement(region, "node", {"id": "dialog"})

        # Global attributes
        ET.SubElement(dialog_node, "attribute", {"id": "category", "type": "LSString", "value": node_tree.category})
        ET.SubElement(dialog_node, "attribute", {"id": "UUID", "type": "FixedString", "value": node_tree.UUID})
        ET.SubElement(dialog_node, "attribute",
                      {"id": "TimelineId", "type": "FixedString", "value": node_tree.TimelineId})

        # Nodes section
        children = ET.SubElement(dialog_node, "children")

        # DefaultAddressedSpeakers
        default_speakers_node = ET.SubElement(children, "node", {"id": "DefaultAddressedSpeakers"})
        default_speakers_children = ET.SubElement(default_speakers_node, "children")
        for speaker in node_tree.DefaultAddressedSpeakers:
            speaker_node = ET.SubElement(default_speakers_children, "node", {"id": "Object", "key": "MapKey"})
            ET.SubElement(speaker_node, "attribute", {"id": "MapKey", "type": "int32", "value": str(speaker.MapKey)})
            ET.SubElement(speaker_node, "attribute",
                          {"id": "MapValue", "type": "int32", "value": str(speaker.MapValue)})

        # Speakers
        speaker_list_node = ET.SubElement(children, "node", {"id": "speakerlist"})
        speaker_list_children = ET.SubElement(speaker_list_node, "children")
        for speaker in node_tree.Speakers:
            speaker_node = ET.SubElement(speaker_list_children, "node", {"id": "speaker", "key": "index"})
            ET.SubElement(speaker_node, "attribute", {"id": "index", "type": "FixedString", "value": speaker.index})
            ET.SubElement(speaker_node, "attribute", {"id": "list", "type": "LSString", "value": speaker.list})
            ET.SubElement(speaker_node, "attribute",
                          {"id": "SpeakerMappingId", "type": "guid", "value": speaker.SpeakerMappingId})

        nodes_section = ET.SubElement(children, "node", {"id": "nodes"})
        nodes_children = ET.SubElement(nodes_section, "children")

        # Generate the XML for each node in the tree
        for node in node_tree.nodes:
            match node:
                case DialogueLineNode():
                    add_dialogue_line_node(nodes_children, node, node_tree)
                case DialogueJumpNode():
                    add_jump_node(nodes_children, node, node_tree)
                case DialogueRollNode():
                    add_roll_node(nodes_children, node, node_tree)
                case DialogueRollResultNode():
                    add_rollresult_node(nodes_children, node, node_tree)
                case DialogueAliasNode():
                    add_alias_node(nodes_children, node, node_tree)
                case DialogueVisualStateNode():
                    add_visualstate_node(nodes_children, node, node_tree)
                case NestedDialogNode():
                    add_nesteddialog_node(nodes_children, node, node_tree)
                case TradeNode():
                    add_trade_node(nodes_children, node, node_tree)
                case _:
                    # Not yet known or unsupported node types
                    print(f"Unknown node type: {type(node).__name__}")

        # RootNodes section at the end
        root_nodes_section = ET.SubElement(nodes_children, "node", {"id": "RootNodes"})
        for node in node_tree.nodes:
            if hasattr(node, 'root') and node.root:
                ET.SubElement(root_nodes_section, "attribute", {
                    "id": "RootNodes",
                    "type": "FixedString",
                    "value": node.uuid
                })

        # Save XML with actual indentation so that it can be deciphered later
        indent_tree(root)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)

class ExportLocalisationOperator(bpy.types.Operator):
    bl_idname = "node.export_localisation"
    bl_label = "Export Localisation"
    bl_description = "Export new (unique) localisation data for the current dialogue"

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if not node_tree or not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "No Dialogue Node Tree found. You should have an open DialogueNodeTree.")
            return {'CANCELLED'}

        # Check if this is a modification of an existing vanilla dialogue
        is_modification = node_tree.is_modification

        # Get localisation file path from preferences
        prefs = context.preferences.addons["Dialog Node Editor"].preferences
        localisation_file = prefs.localisation_path
        if not localisation_file or not os.path.exists(localisation_file):
            self.report({'ERROR'}, "Localisation file path in addon preferences not found or not set.")
            return {'CANCELLED'}

        try:
            if is_modification:
                # Load existing handles from the vanilla loca
                existing_handles = self.load_existing_handles(localisation_file)
                # Compare and get new handles
                new_handles = self.get_new_handles(node_tree, existing_handles)
            else:
                # Get all handles if it's an entirely new dialogue
                new_handles = self.get_all_handles(node_tree)

            if new_handles:
                self.write_localisation_file(new_handles)
                self.report({'INFO'}, f"Localisation exported with {len(new_handles)} handles.")
            else:
                self.report({'WARNING'}, "No new handles to export.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to export localisation: {str(e)}")
            return {'CANCELLED'}

    def load_existing_handles(self, filepath):
        existing_handles = {}
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            for content in root.findall(".//content"):
                contentuid = content.attrib.get("contentuid")
                text = content.text or ""
                if contentuid:
                    existing_handles[contentuid] = text
        except FileNotFoundError:
            self.report({'WARNING'}, f"Localisation file {filepath} not found.")
        except ET.ParseError as e:
            self.report({'ERROR'}, f"Failed to parse localisation file: {str(e)}")
        return existing_handles

    def get_new_handles(self, node_tree, existing_handles):
        new_handles = {}
        for node in node_tree.nodes:
            if hasattr(node, "handles_texts"):
                for handle_text in node.handles_texts:
                    if handle_text.handle not in existing_handles:
                        new_handles[handle_text.handle] = handle_text.text
        return new_handles

    def get_all_handles(self, node_tree):
        handles = {}
        for node in node_tree.nodes:
            if hasattr(node, "handles_texts"):
                for handle_text in node.handles_texts:
                    handles[handle_text.handle] = handle_text.text
        return handles

    # Write localisation file into the directory of the blend file
    def write_localisation_file(self, handles):
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        loc_file = os.path.join(blend_dir, "new_localisation.xml")

        root = ET.Element("contentList")
        for handle, text in handles.items():
            content = ET.SubElement(root, "content", {"contentuid": handle, "version": "1"})
            content.text = text

        # Indent the loca XML
        self.indent_loca_xml(root)

        # Write the XML file
        tree = ET.ElementTree(root)
        with open(loc_file, "wb") as file:
            tree.write(file, encoding="utf-8", xml_declaration=True)

    def indent_loca_xml(self, elem, level=0):
        i = "\n" + "    " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self.indent_loca_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i


# Register operators
def register():
    bpy.utils.register_class(ExportDialogueXML)
    bpy.utils.register_class(ExportLocalisationOperator)

def unregister():
    bpy.utils.unregister_class(ExportLocalisationOperator)
    bpy.utils.unregister_class(ExportDialogueXML)