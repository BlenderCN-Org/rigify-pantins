#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

UI_SLIDERS = '''
import bpy
from mathutils import Matrix, Vector
from math import acos, pi

# rig_id = "%s"


#######################
## Driver namespace  ##
#######################
MEMBER_OFFSET = 0.01
BONE_OFFSET = 0.001

# Members are a group of bones moving together (eg. Hand, Forearm, Arm)
# Bones are individual pieces inside this group
# They can have an extra offset, per bone (eg. eyelid hiding behind the head)

def z_index(member_index, flip, bone_index, extra_offset=0.0):
    """This bone changes sides when the rig is flipped (eg. limbs)"""
    if flip:
        return member_index * MEMBER_OFFSET - bone_index * BONE_OFFSET - extra_offset * MEMBER_OFFSET
    else:
        return member_index * MEMBER_OFFSET + bone_index * BONE_OFFSET + extra_offset * MEMBER_OFFSET

def z_index_same(member_index, flip, bone_index, extra_offset=0.0):
    """This bone does not change sides when the rig is flipped (eg. head)"""
    if flip:
        return -member_index * MEMBER_OFFSET - bone_index * BONE_OFFSET - extra_offset * MEMBER_OFFSET
    else:
        return member_index * MEMBER_OFFSET + bone_index * BONE_OFFSET + extra_offset * MEMBER_OFFSET


#######################
## Swapping operator ##
#######################

class Rigify_Swap_Bones(bpy.types.Operator):
    """ Swap left and right bones
    """
    bl_idname = "pose.rigify_swap_bones"# + rig_id
    bl_label = "Rigify Swap left and right selected bones"
    bl_options = {'UNDO'}


    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.mode == 'POSE')

    def execute(self, context):
        def swap_LR(name):
            if name[-2:] == '.L':
                return name[:-1] + 'R'
            elif name[-2:] == '.R':
                return name[:-1] + 'L'
            else:
                return None

        for pb in context.selected_pose_bones:
            swapped_name = swap_LR(pb.name)
            if swapped_name is not None:
                other = context.object.pose.bones[swapped_name]
                
                tmp_matrix = pb.matrix_basis.copy()
                pb.matrix_basis = other.matrix_basis
                other.matrix_basis = tmp_matrix
        return {'FINISHED'}


###################################
## Bone Z Index Operators and UI ##
###################################

class Rigify_Fill_Members(bpy.types.Operator):
    """Construct member and bone structure"""
    bl_idname = "pose.rigify_fill_members"# + rig_id
    bl_label = "Construct member and bone structure"


    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.object
        
        obj.pantin_members.clear()
        members = {}
        for pbone in obj.pose.bones:
            # print(bone.name)
            if not pbone.bone.use_deform:
                continue
            if not pbone['member_index'] in members:
                members[pbone['member_index']] = []
            members[pbone['member_index']].append((pbone['bone_index'], pbone.name))
        # print(members)
        
        for member, bones in sorted(members.items(), key=lambda i:i[0], reverse=True):
            m = obj.pantin_members.add()
            m.index = member
            for bone in sorted(bones, key=lambda i:i[0], reverse=True):
                b = m.bones.add()
                b.index = bone[0]
                b.name = bone[1]
            
        return {'FINISHED'}

class Rigify_Reapply_Members(bpy.types.Operator):
    """ Change members' order"""
    bl_idname = "pose.rigify_reapply_order_members"# + rig_id
    bl_label = "Reapply previous members' order"
    bl_options = {'UNDO'}


    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.object
        
        for member in obj.pantin_members:
            for bone in member.bones:
                try:
                    pb = obj.pose.bones[bone.name]
                except KeyError:
                    self.report({'WARNING'}, 'Bone {} not found'.format(bone.name))
                    continue
                pb['member_index'] = member.index
                pb['bone_index'] = bone.index
            
        return {'FINISHED'}

class Rigify_Reorder_Members(bpy.types.Operator):
    """ Change members' order"""
    bl_idname = "pose.rigify_reorder_members"# + rig_id
    bl_label = "Change members' order"
    bl_options = {'UNDO'}

    direction = bpy.props.StringProperty()
    list_member_index = bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.object
        # print(self.direction)
        # print(self.list_member_index)
        active_member = obj.pantin_members[self.list_member_index]
        active_member_index = active_member.index

        print('MEMBER:', active_member_index)
        num_members = len(obj.pantin_members)

        tmp = active_member_index
        other_member = None
        if self.direction == 'UP':
            if self.list_member_index > 0:
                other_member = obj.pantin_members[self.list_member_index-1]
                other_member_index = other_member.index

        elif self.direction == 'DOWN':
            if self.list_member_index < num_members-1:
                other_member = obj.pantin_members[self.list_member_index+1]
                other_member_index = other_member.index

        if other_member is not None:
            for b in obj.pose.bones:
                if not b.bone.use_deform:
                    continue
                if b['member_index'] == active_member_index:
                    b['member_index'] = other_member_index
                elif b['member_index'] == other_member_index :
                    b['member_index'] = active_member_index

            # move in UI
            active_member.index = other_member_index
            other_member.index = active_member_index
            if self.direction == 'UP':
                obj.pantin_members.move(self.list_member_index, self.list_member_index-1)
            elif self.direction == 'DOWN':
                obj.pantin_members.move(self.list_member_index, self.list_member_index+1)

                # # move for real
                # active_bone['bone_index'] = next_bone['bone_index']
                # next_bone['bone_index'] = tmp

                # # # move in UI
                # # bone0 = active_member.bones[list_bone_index]
                # # bone1 = active_member.bones[list_bone_index+1]
                # # active_member.bones.move(list_bone_index, list_bone_index + 1)
                # # active_member.active_bone += 1
                # # bone0.index += 1
                # # bone1.index -= 1
            
        mode = bpy.context.mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode=mode)
        
        return {'FINISHED'}

class Rigify_Reorder_Bones(bpy.types.Operator):
    """ Change bones' order"""
    bl_idname = "pose.rigify_reorder_bones"# + rig_id
    bl_label = "Change bones' order"
    bl_options = {'UNDO'}

    direction = bpy.props.StringProperty()
    list_member_index = bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return (context.active_object != None and context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.object
        # print(self.direction)
        # print(self.list_member_index)
        active_member = obj.pantin_members[self.list_member_index]
        active_member_index = active_member.index
        list_bone_index = active_member.active_bone
        rig_bone_index = active_member.bones[active_member.active_bone].index
        print('BONE:', rig_bone_index)
        num_bones = len(active_member.bones)
        # get related bones in rig
        for b in obj.pose.bones:
            if not b.bone.use_deform:
                continue
            if b['member_index'] == active_member_index and b['bone_index'] == rig_bone_index:
                active_bone = b
            if rig_bone_index < num_bones-1 and b['member_index'] == active_member_index and b['bone_index'] == rig_bone_index + 1 :
                previous_bone = b
            if rig_bone_index > 0 and b['member_index'] == active_member_index and b['bone_index'] == rig_bone_index - 1 :
                next_bone = b
        # for b in(previous_bone, active_bone, next_bone):
        #     try:
        #         print(b)
        #     except:
        #         pass
        tmp = active_bone['bone_index']
        if self.direction == 'UP':
            if rig_bone_index < num_bones-1:
                # move for real
                active_bone['bone_index'] = previous_bone['bone_index']
                previous_bone['bone_index'] = tmp
                # move in UI
                bone0 = active_member.bones[list_bone_index]
                bone1 = active_member.bones[list_bone_index-1]
                active_member.bones.move(list_bone_index, list_bone_index - 1)
                active_member.active_bone -= 1
                bone0.index -= 1
                bone1.index += 1

        if self.direction == 'DOWN':
            if rig_bone_index > 0:
                # move for real
                active_bone['bone_index'] = next_bone['bone_index']
                next_bone['bone_index'] = tmp
                # move in UI
                bone0 = active_member.bones[list_bone_index]
                bone1 = active_member.bones[list_bone_index+1]
                active_member.bones.move(list_bone_index, list_bone_index + 1)
                active_member.active_bone += 1
                bone0.index += 1
                bone1.index -= 1
            
        mode = bpy.context.mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode=mode)
        
        return {'FINISHED'}

class PantinBones(bpy.types.PropertyGroup):
    name = bpy.props.StringProperty()
    index = bpy.props.IntProperty()

bpy.utils.register_class(PantinBones)

def member_index_update(self, context):
    """TODODODOD"""
    for m in self.id_data.pantin_members:
        for bone in m.bones:
            self.id_data.pose.bones[bone.name]['member_index'] = m.index

    for b in self.id_data.pose.bones:
        if not b.bone.use_deform:
            continue

        # if b['member_index'] == active_member_index:
        #     b['member_index'] = other_member_index


class PantinMembers(bpy.types.PropertyGroup):
    index = bpy.props.FloatProperty(precision=1, update=member_index_update)
    bones = bpy.props.CollectionProperty(type=bpy.types.PantinBones)
    active_bone = bpy.props.IntProperty()


class PANTIN_UL_bones_list(bpy.types.UIList):
    # The draw_item function is called for each item of the collection that is visible in the list.
    #   data is the RNA object containing the collection,
    #   item is the current drawn item of the collection,
    #   icon is the "computed" icon for the item (as an integer, because some objects like materials or textures
    #   have custom icons ID, which are not available as enum items).
    #   active_data is the RNA object containing the active property for the collection (i.e. integer pointing to the
    #   active item of the collection).
    #   active_propname is the name of the active property (use 'getattr(active_data, active_propname)').
    #   index is index of the current item in the collection.
    #   flt_flag is the result of the filtering process for this item.
    #   Note: as index and flt_flag are optional arguments, you do not have to use/declare them here if you don't
    #         need them.
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        # arm = data
        # draw_item must handle the three layout types... Usually 'DEFAULT' and 'COMPACT' can share the same code.
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(icon='BONE_DATA', text=item.name[4:], translate=False, icon_value=icon)
            row.alignment = 'RIGHT'
            lab = row.label(text=str(item.index), translate=False)
        # 'GRID' layout type should be as compact as possible (typically a single icon!).
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


###################
## Rig UI Panels ##
###################

class DATA_PT_members_panel(bpy.types.Panel):
    bl_label = "Members"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    # bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}
    bl_idname = "PT_members"

    @classmethod
    def poll(self, context):
        if context.mode not in ('POSE', 'OBJECT'):
            return False
        try:
            return ("rig_id" in context.active_object.data)
            # return (context.active_object.data.get("rig_id") == rig_id)
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        C = context
        layout = self.layout
        obj = context.object

        if obj.mode in {'POSE', 'OBJECT'}:

            id_store = C.object

            if id_store.pantin_members and len(id_store.pantin_members):
                box = layout.box()
                col = box.column()
                
                for i, m in enumerate(id_store.pantin_members):
                    row = col.row(align=True)
                    row.alignment = 'EXPAND'
                    row.prop(m, 'index', text="Member")# name.title()+':')
                    op = row.operator("pose.rigify_reorder_members", icon='TRIA_UP', text="")
                    op.list_member_index = i
                    op.direction = 'UP'
                    op = row.operator("pose.rigify_reorder_members", icon='TRIA_DOWN', text="")
                    op.list_member_index = i
                    op.direction = 'DOWN'
                    op = row.operator("pose.rigify_fill_members", icon='FILE_REFRESH', text="")
                    row = col.row()
                    row.template_list("PANTIN_UL_bones_list", "bones", id_store.pantin_members[i], "bones", id_store.pantin_members[i], "active_bone", rows=3)

                    sub = row.column(align=True)
                    op = sub.operator("pose.rigify_reorder_bones", icon='TRIA_UP', text="")
                    op.list_member_index = i
                    op.direction = 'UP'
                    op = sub.operator("pose.rigify_reorder_bones", icon='TRIA_DOWN', text="")
                    op.list_member_index = i
                    op.direction = 'DOWN'

                    col.separator()
            col = layout.column(align=True)
            col.operator("pose.rigify_fill_members")
            col.operator("pose.rigify_reapply_order_members")

class RigUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Rig Main Properties"
    bl_idname = "PT_rig_ui"

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        try:
            return ("rig_id" in context.active_object.data)
            # return (context.active_object.data.get("rig_id") == rig_id)
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        pose_bones = context.active_object.pose.bones
        # bones = context.active_object.data.bones
        try:
            selected_bones = [bone.name for bone in context.selected_pose_bones]
            selected_bones += [context.active_pose_bone.name]
        except (AttributeError, TypeError):
            return

        def is_selected(names):
            # Returns whether any of the named bones are selected.
            if type(names) == list:
                for name in names:
                    if name in selected_bones:
                        return True
            elif names in selected_bones:
                return True
            return False

        layout.operator("pose.rigify_swap_bones")
        layout.separator()

        layout.prop(pose_bones["MCH-Flip"], '["flip"]', text="Flip", slider=True)
        layout.separator()

'''


def layers_ui(layers, layout):
    """ Turn a list of booleans + a list of names into a layer UI.
    """

    code = '''
class RigLayers(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Rig Layers"
    bl_idname = "PT_rig_layers"

    @classmethod
    def poll(self, context):
        try:
            return ("rig_id" in context.active_object.data)
            # return (context.active_object.data.get("rig_id") == rig_id)
        except (AttributeError, KeyError, TypeError):
            return False

    def draw(self, context):
        layout = self.layout
        col = layout.column()
'''
    rows = {}
    for i in range(28):
        if layers[i]:
            if layout[i][1] not in rows:
                rows[layout[i][1]] = []
            rows[layout[i][1]] += [(layout[i][0], i)]

    keys = list(rows.keys())
    keys.sort()

    for key in keys:
        code += "\n        row = col.row()\n"
        i = 0
        for l in rows[key]:
            if i > 3:
                code += "\n        row = col.row()\n"
                i = 0
            code += "        row.prop(context.active_object.data, 'layers', index=%s, toggle=True, text='%s')\n" % (str(l[1]), l[0])
            i += 1

    # Def layer (for parenting)
    code += "\n        row = col.row()"
    code += "\n        row.separator()"
    code += "\n        row = col.row()"
    code += "\n        row.separator()\n"
    code += "\n        row = col.row()\n"
    code += "        row.prop(context.active_object.data, 'layers', index=29, toggle=True, text='Deformation')\n"

    # Root layer
    code += "\n        row = col.row()\n"
    code += "        row.prop(context.active_object.data, 'layers', index=28, toggle=True, text='Root')\n"

    return code


UI_REGISTER = '''

def register():
    bpy.utils.register_class(Rigify_Swap_Bones)
    bpy.utils.register_class(RigUI)
    bpy.utils.register_class(RigLayers)

    bpy.app.driver_namespace["z_index"] = z_index
    bpy.app.driver_namespace["z_index_same"] = z_index_same

    bpy.utils.register_class(Rigify_Fill_Members)
    bpy.utils.register_class(Rigify_Reapply_Members)
    bpy.utils.register_class(Rigify_Reorder_Members)
    bpy.utils.register_class(Rigify_Reorder_Bones)
    bpy.utils.register_class(PantinMembers)
    bpy.utils.register_class(PANTIN_UL_bones_list)
    bpy.utils.register_class(DATA_PT_members_panel)
    bpy.types.Object.pantin_members = bpy.props.CollectionProperty(type=PantinMembers)

def unregister():
    bpy.utils.unregister_class(Rigify_Swap_Bones)
    bpy.utils.unregister_class(RigUI)
    bpy.utils.unregister_class(RigLayers)

    del bpy.app.driver_namespace["z_index"]
    del bpy.app.driver_namespace["z_index_same"]

    del bpy.types.Object.pantin_members
    bpy.utils.unregister_class(Rigify_Fill_Members)
    bpy.utils.unregister_class(Rigify_Reapply_Members)
    bpy.utils.unregister_class(Rigify_Reorder_Members)
    bpy.utils.unregister_class(Rigify_Reorder_Bones)
    bpy.utils.unregister_class(PANTIN_UL_bones_list)
    bpy.utils.unregister_class(DATA_PT_members_panel)
    bpy.utils.unregister_class(PantinMembers)
    bpy.utils.unregister_class(PantinBones)

register()
'''
