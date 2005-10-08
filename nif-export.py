#!BPY

""" 
Name: 'NetImmerse 4.0.0.2 (.nif & .kf))'
Blender: 237
Group: 'Export'
Tip: 'Export the selected objects, along with their parents and children, to a NIF file.'
"""

__author__ = ["amorilia(at)gamebox.net"]
__url__ = ("http://niftools.sourceforge.net/", "blender", "elysiun")
__version__ = "0.7"
__bpydoc__ = """\
The Blender NIF exporter<br>

This script exports a blender model to a NIF file.<br>

Usage:<br>
    - (optional) if you wish to use Morrowind's textures:<br>
      * extract the contents of 'Morrowind.bsa' (and, if you have the expansions, also 'Tribunal.bsa' and 'Bloodmoon.bsa') into 'C:\\MORROWIND'<br>
      * convert all .dds files in 'C:\\MORROWIND\\textures' to .tga files (for instance, using 'DDS Converter 2.1')<br>
    - create meshes (and empties, if you like) in blender:<br>
      * when grouping, always make parent without inverse (in Object Mode, use CTRL-SHIFT-P)<br>
    - create UV coordinates (be sure to check the blender manual for more details)<br>
      * create seams (3D View, Edit Mode, select seam vertices, CTRL-E)<br>
      * in the 3D View, UV Face Select Mode, select all faces, press U->LSCM<br>
      * (optional) if you want to creat your own texture: in the UV/Image Editor, UVs->Save UV Face Layout, and process the saved texture with your favorite 2D paint program<br>
    - add materials to your meshes, and add one texture to each material, with the following settings:<br>
        * texture map input:<br>
            + UV<br>
        * texture map output:<br>
            + COL for diffuse map (base texture)<br>
    - for each texture:<br>
        * set texture type to 'Image'<br>
        * either load a texture from 'C:\\MORROWIND\\textures', or put your custom texture in the 'C:\\Program Files\\Morrowind\\Data Files\\Textures' folder, and load it from there. Note that Blender does not read .dds files.<br>
    - (optional) animate meshes and/or empty objects (press I to insert key, and select Rot, Loc, or LocRot; for now, only location and rotation channels are exported)<br>
    - (optional) Hull your model in a simple so-called collision mesh, which defines where the player cannot walk through (most of Morrowind's static models have a collision mesh, you can see them in the TES CS pressing F4 in the render window). You may want to create it to speed up collision detection, to help the player walk over objects such as stairs, or to allow the player to walk through certain parts of your model such as spider webs.<br>
        * create a mesh called 'RootCollisionNode' (object name, not datablock name)<br>
        * don't apply any material to it
    - (optional) if you suspect that some of the faces of your meshes are not convex, then you should let blender triangulate these meshes (press CTRL-T in edit mode with all vertices selected), because in that case, Blender's triangulation algorithm is less error prone than the triangulation algorithm used in this script.<br>
    - select the models that you wish to export, and run this script from the 'File->Export' menu. Note that the script looks for unparented parents of the selected objects, and exports these root objects along with all of their children, so you don't have to select the whole model.

Notes:<br>
    - Animation may not be exported correctly due to a blender bug (at least in v237): parenting does not correctly update the local transform matrix. Workaround: parent without parent inverse (CTRL-SHIFT-P), and only then apply rotation/translation/scale for animation (for non-animated objects, a workaround is implemented in the exporter).<br>

History:<br>
    - 0.0 (Jun 15): first try<br>
    - 0.1 (Jun 20): fixed texture mapping, fixed transformations, improved error handling<br>
    - 0.2 (Jun 30): export animation, transparency, multiple materials per mesh<br>
    - 0.3 (Aug 25): export normals (fixes lighting, thx y67_a), niflib.py updated<br>
    - 0.4 (Aug 28): support smoothing<br>
    - 0.5 (Sep 26): support for non-textured objects, optimization in trishapedata<br>
    - 0.6 (Sep 27): support for uniformly scaled objects (fixes compatibility problem with Brandano's import script), fixed emissive and ambient colour<br>
    - 0.7 (Sep 30): animation group support (contributed by Moritz Deutsch)<br>

Credits:<br>
    - Brandano, for the import script, which helped a lot writing this export script<br>
    - Taharez, for helping with the Python NIF library, and NIF specs<br>
    - Brick, for NIF specs<br>
    - Shon, for NIF spec updates, and explaining rigging and programming<br>
    - y67_a, for pointing out the fact that the script forgot to export normals; and thereby opening the path to smoothing support<br>
    - Moritz, for non-textured object support, optimizing the main loop in the trishapedata export, and animation group support<br>
"""

# --------------------------------------------------------------------------
# NIF Export v0.7 by Amorilia ( amorilia(at)gamebox.net )
# --------------------------------------------------------------------------
# ***** BEGIN BSD LICENSE BLOCK *****
#
# Copyright (c) 2005, NIF File Format Library and Tools
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#
#    * Neither the name of the NIF File Format Library and Tools
#      project nor the names of its contributors may be used to endorse
#      or promote products derived from this software without specific
#      prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

#
# ***** END BSD LICENCE BLOCK *****
# --------------------------------------------------------------------------

import Blender, struct, re, niflib
from math import sqrt



# 
# Some constants.
# 
epsilon = 0.005       # used for checking equality of floats
show_progress = 1     # 0 = off, 1 = basic, 2 = advanced (but slows down the exporter)
scale_correction = 10 # 1 blender unit = 10 nif units
force_dds = 0         # 0 = use original texture file extension, 1 = force dds extension



#
# A simple custom exception class.
#
class NIFExportError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)



#
# Main export function.
#
def export_nif(filename):
    try: # catch NIFExportErrors
        
        # preparation:
        #--------------
        if show_progress >= 1: Blender.Window.DrawProgressBar(0.0, "Preparing Export")

        # strip extension from filename
        root_name, fileext = Blender.sys.splitext(Blender.sys.basename(filename))
        # get the root object from selected object
        if (Blender.Object.GetSelected() == None):
            raise NIFExportError("Please select the object(s) that you wish to export, and run this script again.")
        root_objects = []
        for root_object in Blender.Object.GetSelected():
            while (root_object.getParent() != None):
                root_object = root_object.getParent()
            if ((root_object.getType() != 'Empty') and (root_object.getType() != 'Mesh')):
                raise NIFExportError("Root object (%s) must be an 'Empty' or a 'Mesh' object."%root_object.getName())
            if (root_objects.count(root_object) == 0): root_objects.append(root_object)

        # exporting:
        #------------
        if show_progress >= 1: Blender.Window.DrawProgressBar(0.33, "Converting to NIF")

        # create an empty nif object
        nif = niflib.NIF()
        
        # setup my anim export flag
        nif.animextra = 0
        
        # export the root node (note that transformation is ignored on the root node)
        nif = export_node(None, 'none', -1, 1.0, root_name, nif)
        for root_object in root_objects:
            # export the root objects as a NiNodes; their children are exported as well
            nif = export_node(root_object, 'worldspace', 0, scale_correction, root_object.getName(), nif)

        # write the file:
        #-----------------
        if show_progress >= 1: Blender.Window.DrawProgressBar(0.66, "Writing NIF file")
        
        if ((fileext != '.nif') and (fileext != '.NIF')):
            filename += '.nif'
        file = open(filename, "wb")
        try:
            nif.write(file)
        finally:
            # clean up: close file
            file.close()
        
        if ( nif.animextra == 1 ):
            # if animation groups were detected during export:
            # create a copy of the nif named Xbasename.nif
            # perhaps one should remove those animation data from that file
            # but it work with a simple copy too
            nam, ext = Blender.sys.splitext(Blender.sys.basename(filename))
            xnf_filename = Blender.sys.join( Blender.sys.dirname( filename ), 'X' + nam + '.nif' )
            xnf_file = open( xnf_filename, "wb" )
            try:
                nif.write( xnf_file )
            finally:
                xnf_file.close()
            # and create Xbasename.kf animation stream helper file
            export_kf( nif, filename );

    except NIFExportError, e: # in that case, we raise a menu instead of an exception
        if show_progress >= 1: Blender.Window.DrawProgressBar(1.0, "Export Failed")
        print 'NIFExportError: ' + e.value
        Blender.Draw.PupMenu('ERROR%t|' + e.value)
        return

    # no export error, but let's double check: try reading the file we just wrote
    # we can probably remove these lines once the exporter is stable
    if show_progress >= 1: Blender.Window.DrawProgressBar(1.0, "Finished")
    nif.dump()
    try:
        nif = niflib.NIF()
        file = open(filename, "rb")
        nif.read(file)
        file.close()
    except:
        Blender.Draw.PupMenu("WARNING%t|Exported NIF file may not be valid: double check failed! This is probably due to an unknown bug in the exporter code.")
        raise # re-raise the exception


#
# export .kf file
#
def export_kf(NF, filename):
    # strip extension from filename
    nam, ext = Blender.sys.splitext(Blender.sys.basename(filename))

    kf_filename = Blender.sys.join( Blender.sys.dirname( filename ), 'X' + nam + '.kf' )

    KF = niflib.NIF()
    KF.blocks.append( niflib.NiSequenceStreamHelper() )
    KF.blocks[0].block_type.value = 'NiSequenceStreamHelper'
    KF.header.nblocks += 1

    lastextra  = -1
    controller = []

    # save extra text data
    for block in NF.blocks:
        if block.block_type.value == 'NiTextKeyExtraData':
            assert ( lastextra < 0 )
            KF.blocks.append( block )
            KF.blocks[0].extra_data_id = KF.header.nblocks
            lastextra = KF.header.nblocks
            KF.header.nblocks += 1

    # find nodes with keyframe controller
    for block in NF.blocks:
        if block.block_type.value == "NiNode" or block.block_type.value == "NiBSAnimationNode":
            if block.controller_id >= 0:
                controller.append( block.controller_id )
                # link to the original node with a NiStringExtraData
                KF.blocks[lastextra].extra_data_id = KF.header.nblocks
                lastextra = KF.header.nblocks + 1
                S = niflib.NiStringExtraData()
                S.block_type.value = 'NiStringExtraData'
                S.string_data.value = block.name.value
                S.dunno = 4 + len( S.string_data.value ) # length of the string_data
                KF.blocks.append( S )
                KF.header.nblocks += 1

    # copy keyframe controllers and keyframe datas
    assert ( len( controller ) > 0 )
    lastctrl = 0
    for cid in controller:
        C = NF.blocks[ cid ]

        if ( lastctrl == 0 ):
            KF.blocks[ lastctrl ].controller_id = KF.header.nblocks
        else:
            KF.blocks[ lastctrl ].next_controller_id = KF.header.nblocks
        
        KF.blocks.append( C )
        lastctrl = KF.header.nblocks
        KF.header.nblocks += 1

        assert ( C.data_id > 0 )

        KF.blocks.append( NF.blocks[ C.data_id ] )
        KF.blocks[ lastctrl ].parent_id = -1
        KF.blocks[ lastctrl ].data_id = KF.header.nblocks
        KF.header.nblocks += 1

    # write .KF file
    print "writing %s file"%kf_filename
    KF.dump()
    kf_file = open( kf_filename, "wb" )
    KF.write( kf_file )
    kf_file.close()


# 
# Export a mesh/empty object ob, child of nif block parent_block_id, as a
# NiNode block. Export also all children of ob, and return the updated
# nif.
#
# - space is 'none', 'worldspace', or 'localspace', and determines
#   relative to what object the transformation should be stored.
# - parent_block_id is the block index of the parent of the object (-1
#   for the root node)
# - for the root node, ob is None, and node_name is usually the base
#   filename (either with or without extension)
#
def export_node(ob, space, parent_block_id, parent_scale, node_name, nif):
    ipo = None
    ob_block_id = nif.header.nblocks # the block index number of the to be created block
    assert(ob_block_id == len(nif.blocks)) # debug

    # determine the block type, and append a new node to the nif block list
    if (ob == None):
        # -> root node
        assert(parent_block_id == -1) # debug
        assert(nif.header.nblocks == 0) # debug
        nif.blocks.append(niflib.NiNode())
        nif.blocks[ob_block_id].block_type.value = 'NiNode'
    else:
        assert((ob.getType() == 'Empty') or (ob.getType() == 'Mesh')) # debug
        assert(parent_block_id >= 0) # debug
        assert(nif.header.nblocks >= 1) # debug
        ipo = ob.getIpo() # get animation data
        if (ob.getName() == 'RootCollisionNode'):
            # -> root collision node
            # we export the root collision node as a child of the root node
            parent_block_id = 0
            space = 'worldspace'
            node_name = ''
            if (ipo != None):
                raise NIFExportError('ERROR%t|RootCollisionNode should not be animated.')
            nif.blocks.append(niflib.RootCollisionNode())
            nif.blocks[ob_block_id].block_type.value = 'RootCollisionNode'
        elif (ipo == None):
            # -> static object
            nif.blocks.append(niflib.NiNode())
            nif.blocks[ob_block_id].block_type.value = 'NiNode'
        else:
            # -> animated object
            nif.blocks.append(niflib.NiBSAnimationNode())
            nif.blocks[ob_block_id].block_type.value = 'NiBSAnimationNode'
    
    nif.header.nblocks += 1

    # make it child of its parent in the nif, if it has one
    if (parent_block_id >= 0):
        nif.blocks[parent_block_id].child_id.append(ob_block_id)
        nif.blocks[parent_block_id].num_children += 1
    
    # and fill in this node's non-trivial values
    nif.blocks[ob_block_id].name.value = node_name
    if (ob == None):
        nif.blocks[ob_block_id].flags = 0x000C # ? this seems pretty standard for the root node
    elif (ob.getName() == 'RootCollisionNode'):
        nif.blocks[ob_block_id].flags = 0x0003 # ? this seems pretty standard for the root collision node
    elif (ipo == None):
        nif.blocks[ob_block_id].flags = 0x000C # ? this seems pretty standard for static ninodes
    else:
        nif.blocks[ob_block_id].flags = 0x006A # ? this seems pretty standard for animated ninodes        

    # if scale of NiNodes is not 1.0, then the engine does a bit
    # weird... let's play safe and require it to be 1.0
    nif.blocks[ob_block_id].translation, \
    nif.blocks[ob_block_id].rotation, \
    scale, \
    nif.blocks[ob_block_id].velocity  \
    = export_matrix(ob, space)
    nif.blocks[ob_block_id].scale = 1.0; # scale is taken into account under export_trishapes and export_children below
    # take care of the parent scale
    nif.blocks[ob_block_id].translation.x *= parent_scale
    nif.blocks[ob_block_id].translation.y *= parent_scale
    nif.blocks[ob_block_id].translation.z *= parent_scale

    if (ob != None):
        # export animation
        if (ipo != None):
            nif = export_keyframe(ob, space, ob_block_id, parent_scale, nif)
    
        # if it is a mesh, export the mesh as trishape children of this ninode
        # (we assume scale.x == scale.y == scale.z)
        if (ob.getType() == 'Mesh'):
            nif = export_trishapes(ob, 'none', ob_block_id, parent_scale * scale.x, nif) # the transformation of the mesh is already in the ninode block (except for scaling)

        # export all children of this empty/mesh object as children of this NiNode
        return export_children(ob, ob_block_id, parent_scale * scale.x, nif)
    else:
        return nif



#
# Export the animation of blender object ob as keyframe controller and keyframe data.
#
def export_keyframe(ob, space, parent_block_id, parent_scale, nif):
    # -> get keyframe information

    #assert(space == 'localspace')

    # get frame start and frame end, and the number of frames per second
    scn = Blender.Scene.GetCurrent()
    context = scn.getRenderingContext()
 
    fspeed = 1.0 / context.framesPerSec()
    fstart = context.startFrame()
    fend = context.endFrame()

    # merge the animation curves into a rotation vector and translation vector curve
    ipo = ob.getIpo()
    assert(ipo != None) # debug
    rot_curve = {}
    trans_curve = {}
    for curve in ipo.getCurves():
        for btriple in curve.getPoints():
            knot = btriple.getPoints()
            frame = knot[0]
            ftime = (frame - 1) * fspeed
            if (curve.getName() == 'RotX') or (curve.getName() == 'RotY') or (curve.getName() == 'RotZ'):
                rot_curve[ftime] = Blender.Mathutils.Euler([10*ipo.getCurve('RotX').evaluate(frame), 10*ipo.getCurve('RotY').evaluate(frame), 10*ipo.getCurve('RotZ').evaluate(frame)]).toQuat()
            if (curve.getName() == 'LocX') or (curve.getName() == 'LocY') or (curve.getName() == 'LocZ'):
                trans_curve[ftime] = niflib.NiVector()
                trans_curve[ftime].x = ipo.getCurve('LocX').evaluate(frame) * parent_scale
                trans_curve[ftime].y = ipo.getCurve('LocY').evaluate(frame) * parent_scale
                trans_curve[ftime].z = ipo.getCurve('LocZ').evaluate(frame) * parent_scale

    # -> now comes the real export
    last_id = nif.header.nblocks - 1


    # check for animation group definitions

    # timeline markers are not supported yet
    # so get the anim group definitions from a text buffer

    txtlist = Blender.Text.Get()
    for animtxt in txtlist:
        if animtxt.getName() == "Anim":
            break
    else:
        animtxt = None

    if animtxt != None and nif.animextra == 0:
        # parse the anim text descriptor

	# format is:
	# frame/string1[/string2[.../stringN]]

	# example:
	# 000/Idle: Start/Idle: Stop/Idle2: Start/Idle2: Loop Start
	# 050/Idle2: Stop/Idle3: Start
	# 100/Idle3: Loop Start/Idle3: Stop

        slist = animtxt.asLines()
        flist = []
        dlist = []
        for s in slist:
            t = s.split( '/' )
            if ( len( t ) > 1 ):
                f = int( t[0] )
                d = ''
                for i in range( 1, len( t ) ):
                    if ( i > 1 ):
                        d = d + '\r\n' + t[i].strip( ' ' )
                    else:
                        d = d + t[i].strip( ' ' )
                print 'frame %d'%f + ' -> \'%s\''%d
                flist.append( f )
                dlist.append( d )

        if ( len( flist ) > 0 ):    
            # add a NiTextKeyExtraData block, and refer to this block in the parent node
            textextra_id = last_id + 1
            last_id = textextra_id
            assert(textextra_id == len(nif.blocks)) # debug
            nif.blocks.append(niflib.NiTextKeyExtraData())
            nif.blocks[textextra_id].block_type.value = 'NiTextKeyExtraData'
            assert(nif.blocks[parent_block_id].extra_data_id == -1) # make sure we don't overwrite anything
            nif.blocks[parent_block_id].extra_data_id = textextra_id
            nif.header.nblocks += 1
    
            # create a NiTextKey for each frame descriptor
            nif.blocks[textextra_id].num_keys = len( flist )
            for i in range( len( flist ) ):
                nif.blocks[textextra_id].text_key.append( niflib.NiTextKey() )
                nif.blocks[textextra_id].text_key[i].time = fspeed * flist[i];
                nif.blocks[textextra_id].text_key[i].name.value = dlist[i];
    
            # remove 'play loop' from parent node
            if nif.blocks[parent_block_id].flags == 0x6a:
                nif.blocks[parent_block_id].flags = 0x0a
            
            # raise the flag
            nif.animextra = 1


    # add a keyframecontroller block, and refer to this block in the parent's time controller
    keyframectrl_id = last_id + 1
    last_id = keyframectrl_id
    assert(keyframectrl_id == len(nif.blocks)) # debug
    nif.blocks.append(niflib.NiKeyframeController()) # this should be block[keyframectrl_id]
    nif.blocks[keyframectrl_id].block_type.value = 'NiKeyframeController'
    assert(nif.blocks[parent_block_id].controller_id == -1) # make sure we don't overwrite anything
    nif.blocks[parent_block_id].controller_id = keyframectrl_id
    nif.header.nblocks += 1

    # fill in the non-trivial values
    nif.blocks[keyframectrl_id].flags = 0x0008
    nif.blocks[keyframectrl_id].frequency = 1.0
    nif.blocks[keyframectrl_id].phase = 0.0
    nif.blocks[keyframectrl_id].start_time = (fstart - 1) * fspeed
    nif.blocks[keyframectrl_id].stop_time = (fend - fstart) * fspeed
    nif.blocks[keyframectrl_id].parent_id = parent_block_id

    # add the keyframe data
    keyframedata_id = last_id + 1
    last_id = keyframedata_id
    assert(keyframedata_id == len(nif.blocks)) # debug
    nif.blocks.append(niflib.NiKeyframeData()) # this should be block[keyframedata_id]
    nif.blocks[keyframedata_id].block_type.value = 'NiKeyframeData'
    nif.blocks[keyframectrl_id].data_id = keyframedata_id
    nif.header.nblocks += 1

    nif.blocks[keyframedata_id].rotation_frame_type = 1
    ftimes = rot_curve.keys()
    ftimes.sort()
    for ftime in ftimes:
        rot_frame = niflib.NiRotFrame(1)
        rot_frame.time = ftime
        rot_frame.quat[0] = rot_curve[ftime].w
        rot_frame.quat[1] = rot_curve[ftime].x
        rot_frame.quat[2] = rot_curve[ftime].y
        rot_frame.quat[3] = rot_curve[ftime].z
        nif.blocks[keyframedata_id].rotation_frame.append(rot_frame)
    nif.blocks[keyframedata_id].num_rotation_frames = len(nif.blocks[keyframedata_id].rotation_frame)

    trans_count = 0
    nif.blocks[keyframedata_id].translation_frame_type = 1
    ftimes = trans_curve.keys()
    ftimes.sort()
    for ftime in ftimes:
        trans_frame = niflib.NiTransFrame(1)
        trans_frame.time = ftime
        trans_frame.translation.x = trans_curve[ftime].x
        trans_frame.translation.y = trans_curve[ftime].y
        trans_frame.translation.z = trans_curve[ftime].z
        nif.blocks[keyframedata_id].translation_frame.append(trans_frame)
    nif.blocks[keyframedata_id].num_translation_frames = len(nif.blocks[keyframedata_id].translation_frame)

    return nif



#
# Export a blender object ob of the type mesh, child of nif block
# parent_block_id, as NiTriShape and NiTriShapeData blocks, possibly
# along with some NiTexturingProperty, NiSourceTexture,
# NiMaterialProperty, and NiAlphaProperty blocks. We export one
# trishape block per mesh material.
# 
def export_trishapes(ob, space, parent_block_id, parent_scale, nif):
    assert(ob.getType() == 'Mesh')

    # get mesh from ob
    mesh = Blender.NMesh.GetRaw(ob.data.name)

    # get the mesh's materials
    mesh_mats = mesh.getMaterials(1) # the argument guarantees that the material list agrees with the face material indices
    
    # if the mesh has no materials, all face material indices should be 0, so it's ok to fake one material in the material list
    if (mesh_mats == []):
        mesh_mats = [ None ]
    
    # let's now export one trishape for every mesh material
    
    materialIndex = 0 # material index of the current mesh material
    for mesh_mat in mesh_mats:
        # -> first, extract valuable info from our ob
        
        mesh_base_tex = None
        mesh_hasalpha = 0
        mesh_hastex = 0
        if (mesh_mat != None):
            mesh_mat_ambient = mesh_mat.getAmb()             # 'Amb' scrollbar in blender (MW -> 1.0 1.0 1.0)
            mesh_mat_diffuse_colour = mesh_mat.getRGBCol()   # 'Col' colour in Blender (MW -> 1.0 1.0 1.0)
            mesh_mat_specular_colour = mesh_mat.getSpecCol() # 'Spe' colour in Blender (MW -> 0.0 0.0 0.0)
            mesh_mat_emissive = mesh_mat.getEmit()           # 'Emit' scrollbar in Blender (MW -> 0.0 0.0 0.0)
            mesh_mat_shininess = mesh_mat.getSpec() / 2.0    # 'Spec' scrollbar in Blender, takes values between 0.0 and 2.0 (MW -> 0.0)
            mesh_mat_transparency = mesh_mat.getAlpha()      # 'A(lpha)' scrollbar in Blender (MW -> 1.0)
            mesh_hasalpha = (abs(mesh_mat_transparency - 1.0) > epsilon)
            # the base texture = first material texture
            # note that most morrowind files only have a base texture, so let's for now only support single textured materials
            for mtex in mesh_mat.getTextures():
                if (mtex != None):
                    if (mesh_base_tex == None):
                        if (mtex.texco != Blender.Texture.TexCo.UV):
                            # nif only support UV-mapped textures
                            raise NIFExportError("Non-UV texture in mesh '%s', material '%s'. Either delete all non-UV textures, or in the Shading Panel, under Material Buttons, set texture 'Map Input' to 'UV'."%(ob.getName(),mesh_mat.getName()))
                        if (mtex.mapto != Blender.Texture.MapTo.COL):
                            # it should map to colour
                            raise NIFExportError("Non-COL-mapped texture in mesh '%s', material '%s', these cannot be exported to NIF. Either delete all non-COL-mapped textures, or in the Shading Panel, under Material Buttons, set texture 'Map To' to 'COL'."%(mesh.getName(),mesh_mat.getName()))
                        # got the base texture
                        mesh_base_tex = mtex.tex
                        mesh_hastex = 1
                    else:
                        raise NIFExportError("Multiple textures in mesh '%s', material '%s', this is not supported. Delete all textures, except for the base texture."%(mesh.getName(),mesh_mat.getName()))

        # note: we can be in any of the following three situations
        # material + base texture       -> normal object
        # material, but no base texture -> uniformly coloured object
        # no material                   -> typically, collision mesh

        # -> now comes the real export
        last_id = nif.header.nblocks - 1
        
        # add a trishape block, and refer to this block in the parent's children list
        trishape_id = last_id + 1
        last_id = trishape_id
        assert(trishape_id == len(nif.blocks)) # debug
        nif.blocks.append(niflib.NiTriShape()) # this should be block[trishape_id]
        nif.blocks[trishape_id].block_type.value = 'NiTriShape'
        nif.blocks[parent_block_id].child_id.append(trishape_id)
        nif.blocks[parent_block_id].num_children += 1
        nif.header.nblocks += 1
        
        # fill in the NiTriShape's non-trivial values
        if (nif.blocks[parent_block_id].name.value != ""):
            nif.blocks[trishape_id].name.value = "Tri " + nif.blocks[parent_block_id].name.value + " %i"%(nif.blocks[parent_block_id].num_children-1) # Morrowind's child naming convention
        nif.blocks[trishape_id].flags = 0x0004 # ? this seems standard
        nif.blocks[trishape_id].translation, \
        nif.blocks[trishape_id].rotation, \
        scale, \
        nif.blocks[trishape_id].velocity \
        = export_matrix(ob, space)
        # scale correction
        nif.blocks[trishape_id].translation.x *= parent_scale
        nif.blocks[trishape_id].translation.y *= parent_scale
        nif.blocks[trishape_id].translation.z *= parent_scale
        # scaling is applied on vertices... here we put it on 1.0
        nif.blocks[trishape_id].scale = 1.0;
        final_scale = parent_scale * scale.x;
        
        if (mesh_base_tex != None):
            # add NiTriShape's texturing property
            tritexprop_id = last_id + 1
            last_id = tritexprop_id
            assert(tritexprop_id == len(nif.blocks)) # debug
            nif.blocks.append(niflib.NiTexturingProperty())
            nif.blocks[tritexprop_id].block_type.value = 'NiTexturingProperty'
            nif.blocks[trishape_id].property_id.append(tritexprop_id)
            nif.blocks[trishape_id].num_properties += 1
            nif.header.nblocks += 1
            
            nif.blocks[tritexprop_id].flags = 0x0001 # ? standard
            nif.blocks[tritexprop_id].apply_mode = 2 # modulate?
            nif.blocks[tritexprop_id].dunno1 = 7 # ? standard
            
            nif.blocks[tritexprop_id].has_base_tex = 1
            nif.blocks[tritexprop_id].base_tex.clamp_mode = 3 # wrap in both directions
            nif.blocks[tritexprop_id].base_tex.set = 2 # ? standard (usually 2, but 0 and 1 are also possible)
            nif.blocks[tritexprop_id].base_tex.dunno1 = 0 # ? standard
            nif.blocks[tritexprop_id].base_tex.ps2_l = 0 # ? standard 
            nif.blocks[tritexprop_id].base_tex.ps2_k = -75 # ? standard
            nif.blocks[tritexprop_id].base_tex.dunno2 = 0x0101 # ? standard
            
            # add NiTexturingProperty's texture source
            tritexsrc_id = last_id + 1
            last_id = tritexsrc_id
            assert(tritexsrc_id == len(nif.blocks)) # debug
            nif.blocks.append(niflib.NiSourceTexture())
            nif.blocks[tritexsrc_id].block_type.value = 'NiSourceTexture'
            nif.blocks[tritexprop_id].base_tex.source_id = tritexsrc_id
            nif.header.nblocks += 1
            
            nif.blocks[tritexsrc_id].external = 1
            nif.blocks[tritexsrc_id].texture_file_name.value = Blender.sys.basename(mesh_base_tex.image.getFilename())
            if force_dds:
                nif.blocks[tritexsrc_id].texture_file_name.value = nif.blocks[tritexsrc_id].texture_file_name.value[:-4] + '.dds'
            nif.blocks[tritexsrc_id].pixel_layout = 5 # default?
            nif.blocks[tritexsrc_id].mipmap = 2 # default?
            nif.blocks[tritexsrc_id].alpha = 3 # default?
            nif.blocks[tritexsrc_id].dunno1 = 1 # ?
            
        if (mesh_hasalpha):
            # add NiTriShape's alpha propery (this is de facto an automated version of Detritus's method, see http://detritus.silgrad.com/alphahex.html)
            trialphaprop_id = last_id + 1
            last_id = trialphaprop_id
            assert(trialphaprop_id == len(nif.blocks))
            nif.blocks.append(niflib.NiAlphaProperty())
            nif.blocks[trialphaprop_id].block_type.value = 'NiAlphaProperty'
            nif.header.nblocks += 1
            
            nif.blocks[trialphaprop_id].flags = 0x00ED
            nif.blocks[trialphaprop_id].dunno = 0
            
            # refer to the alpha property in the trishape block
            nif.blocks[trishape_id].property_id.append(trialphaprop_id)
            nif.blocks[trishape_id].num_properties += 1

        if (mesh_mat_shininess > epsilon ):
            # add NiTriShape's specular property
            trispecprop_id = last_id + 1
            last_id = trispecprop_id
            assert(trispecprop_id == len(nif.blocks))
            nif.blocks.append(niflib.NiSpecularProperty())
            nif.blocks[trispecprop_id].block_type.value = 'NiSpecularProperty'
            nif.header.nblocks += 1
            
            nif.blocks[trispecprop_id].flags = 0x0001
            
            # refer to the specular property in the trishape block
            nif.blocks[trishape_id].property_id.append(trispecprop_id)
            nif.blocks[trishape_id].num_properties += 1
            
        if (mesh_mat != None):
            # add NiTriShape's material property
            trimatprop_id = last_id + 1
            last_id = trimatprop_id
            assert(trimatprop_id == len(nif.blocks))
            nif.blocks.append(niflib.NiMaterialProperty())
            nif.blocks[trimatprop_id].block_type.value = 'NiMaterialProperty'
            nif.header.nblocks += 1
            
            nif.blocks[trimatprop_id].name.value = mesh_mat.getName()
            nif.blocks[trimatprop_id].flags = 0x0001 # ? standard
            nif.blocks[trimatprop_id].ambient_colour.r = mesh_mat_ambient * mesh_mat_diffuse_colour[0]
            nif.blocks[trimatprop_id].ambient_colour.g = mesh_mat_ambient * mesh_mat_diffuse_colour[1]
            nif.blocks[trimatprop_id].ambient_colour.b = mesh_mat_ambient * mesh_mat_diffuse_colour[2]
            nif.blocks[trimatprop_id].diffuse_colour.r = mesh_mat_diffuse_colour[0]
            nif.blocks[trimatprop_id].diffuse_colour.g = mesh_mat_diffuse_colour[1]
            nif.blocks[trimatprop_id].diffuse_colour.b = mesh_mat_diffuse_colour[2]
            nif.blocks[trimatprop_id].specular_colour.r = mesh_mat_specular_colour[0]
            nif.blocks[trimatprop_id].specular_colour.g = mesh_mat_specular_colour[1]
            nif.blocks[trimatprop_id].specular_colour.b = mesh_mat_specular_colour[2]
            nif.blocks[trimatprop_id].emissive_colour.r = mesh_mat_emissive * mesh_mat_diffuse_colour[0]
            nif.blocks[trimatprop_id].emissive_colour.g = mesh_mat_emissive * mesh_mat_diffuse_colour[1]
            nif.blocks[trimatprop_id].emissive_colour.b = mesh_mat_emissive * mesh_mat_diffuse_colour[2]
            nif.blocks[trimatprop_id].shininess = mesh_mat_shininess
            nif.blocks[trimatprop_id].transparency = mesh_mat_transparency
            
            # refer to the material property in the trishape block
            nif.blocks[trishape_id].property_id.append(trimatprop_id)
            nif.blocks[trishape_id].num_properties += 1
        
        # add NiTriShape's data
        tridata_id = last_id + 1
        last_id = tridata_id
        assert(tridata_id == len(nif.blocks))
        nif.blocks.append(niflib.NiTriShapeData())
        nif.blocks[tridata_id].block_type.value = 'NiTriShapeData'
        nif.blocks[trishape_id].data_id = tridata_id
        nif.header.nblocks += 1
        
        # set faces, vertices, uv-vertices, and normals
        nif.blocks[tridata_id].has_vertices = 1 # ? not sure what non-zero value to choose
        if (mesh_hastex):
            nif.blocks[tridata_id].has_uv_vertices = 1 # ? not sure what non-zero value to choose
            nif.blocks[tridata_id].num_texture_sets = 1 # for now, we only have one texture for this trishape
        else:
            nif.blocks[tridata_id].has_uv_vertices = 0
            nif.blocks[tridata_id].num_texture_sets = 0
        if (mesh_mat != None):
            nif.blocks[tridata_id].has_normals = 1 # if we have a material, we should add normals for proper lighting
        else:
            nif.blocks[tridata_id].has_normals = 0
        nif.blocks[tridata_id].uv_vertex = [ [] ] * nif.blocks[tridata_id].num_texture_sets # uv_vertex now has num_texture_sets elements, namely, an empty list of uv vertices for each 'texture set'

        # Blender only supports one set of uv coordinates per mesh;
        # therefore, we shall have trouble when importing
        # multi-textured trishapes in blender. For this export script,
        # no problem: we must simply duplicate the uv vertex list.

        # We now extract vertices, uv-vertices, and normals from the
        # mesh's face list. NIF has one uv vertex and one normal per
        # vertex, unlike blender's uv vertices and normals per
        # face... therefore some vertices must be duplicated. The
        # following algorithm extracts all unique (vert, uv-vert,
        # normal) pairs, and uses this list to produce the list of
        # vertices, uv-vertices, normals, and face indices.

        # NIF uses the normal table for lighting. So, smooth faces
        # should use Blender's vertex normals, and solid faces should
        # use Blender's face normals.
        
        verttriple_list = [] # (vertex, uv coordinate, normal) list
        count = 0
        for f in mesh.faces:
            if show_progress >= 2: Blender.Window.DrawProgressBar(0.33 * float(count)/len(mesh.faces), "Converting to NIF (%s)"%ob.getName())
            count += 1
            # does the face belong to this trishape?
            if (mesh_mat != None): # we have a material
                if (f.materialIndex != materialIndex): # but this face has another material
                    continue # so skip this face
            f_numverts = len(f.v)
            assert((f_numverts == 3) or (f_numverts == 4)) # debug
            if (nif.blocks[tridata_id].has_uv_vertices):
                if (len(f.uv) != len(f.v)): # make sure we have UV data
                    raise NIFExportError('ERROR%t|Create a UV map for every texture, and run the script again.')
            # find (vert, uv-vert, normal) triple, and if not found, create it
            f_index = [ -1 ] * f_numverts
            for i in range(f_numverts):
                fv = niflib.NiVector()
                fv.x = f.v[i][0] * final_scale
                fv.y = f.v[i][1] * final_scale
                fv.z = f.v[i][2] * final_scale
                # get vertex normal for lighting (smooth = Blender vertex normal, non-smooth = Blender face normal)
                fn = niflib.NiVector()
                if nif.blocks[tridata_id].has_normals:
                    if f.smooth:
                        fn.x = f.v[i].no[0]
                        fn.y = f.v[i].no[1]
                        fn.z = f.v[i].no[2]
                    else:
                        fn.x = f.no[0]
                        fn.y = f.no[1]
                        fn.z = f.no[2]
                else:
                    fn = None
                if (nif.blocks[tridata_id].has_uv_vertices):
                    fuv = niflib.NiUV()
                    fuv.u = f.uv[i][0]
                    fuv.v = 1.0 - f.uv[i][1] # NIF flips the texture V-coordinate (OpenGL standard)
                else:
                    fuv = None
                # do we already have this triple? (optimized by m4444x)
                verttriple = ( fv, fuv, fn )
                f_index[i] = len(verttriple_list)
                for j in range(len(verttriple_list)):
                    if abs(verttriple[0].x - verttriple_list[j][0].x) > epsilon: continue
                    if abs(verttriple[0].y - verttriple_list[j][0].y) > epsilon: continue
                    if abs(verttriple[0].z - verttriple_list[j][0].z) > epsilon: continue
                    if nif.blocks[tridata_id].has_uv_vertices:
                        if abs(verttriple[1].u - verttriple_list[j][1].u) > epsilon: continue
                        if abs(verttriple[1].v - verttriple_list[j][1].v) > epsilon: continue
                    if nif.blocks[tridata_id].has_normals:
                        if abs(verttriple[2].x - verttriple_list[j][2].x) > epsilon: continue
                        if abs(verttriple[2].y - verttriple_list[j][2].y) > epsilon: continue
                        if abs(verttriple[2].z - verttriple_list[j][2].z) > epsilon: continue
                    # all tests passed: so yes, we already have it!
                    f_index[i] = j
                    break
                if (f_index[i] == len(verttriple_list)):
                    # new (vert, uv-vert, normal) triple: add it
                    verttriple_list.append(verttriple)
                    # add the vertex
                    nif.blocks[tridata_id].vertex.append(fv)
                    # and add the vertex normal
                    if (nif.blocks[tridata_id].has_normals):
                        nif.blocks[tridata_id].normal.append(fn)
                    # for each texture set, add the uv-vertex
                    if (nif.blocks[tridata_id].has_uv_vertices):
                        for texset in range(nif.blocks[tridata_id].num_texture_sets):
                            nif.blocks[tridata_id].uv_vertex[texset].append(fuv)
            # now add the (hopefully, convex) face, in triangles
            for i in range(f_numverts - 2):
                f_indexed = niflib.NiFace()
                f_indexed.vert1 = f_index[0]
                if (final_scale > 0):
                    f_indexed.vert2 = f_index[1+i]
                    f_indexed.vert3 = f_index[2+i]
                else:
                    f_indexed.vert2 = f_index[2+i]
                    f_indexed.vert3 = f_index[1+i]
                nif.blocks[tridata_id].face.append(f_indexed)

        # update the counters
        nif.blocks[tridata_id].num_vertices = len(verttriple_list)
        nif.blocks[tridata_id].num_faces = len(nif.blocks[tridata_id].face)
        nif.blocks[tridata_id].num_faces_x_3 = nif.blocks[tridata_id].num_faces * 3

        # center
        count = 0
        for v in mesh.verts:
            if show_progress >= 2: Blender.Window.DrawProgressBar(0.33 + 0.33 * float(count)/len(mesh.verts), "Converting to NIF (%s)"%ob.getName())
            count += 1
            nif.blocks[tridata_id].center.x += v[0]
            nif.blocks[tridata_id].center.y += v[1]
            nif.blocks[tridata_id].center.z += v[2]
        assert(len(mesh.verts) > 0) # debug
        nif.blocks[tridata_id].center.x /= len(mesh.verts)
        nif.blocks[tridata_id].center.y /= len(mesh.verts)
        nif.blocks[tridata_id].center.z /= len(mesh.verts)
        
        # radius
        count = 0
        for v in mesh.verts:
            if show_progress >= 2: Blender.Window.DrawProgressBar(0.66 + 0.33 * float(count)/len(mesh.verts), "Converting to NIF (%s)"%ob.getName())
            count += 1
            r = get_distance(v, nif.blocks[tridata_id].center)
            if (r > nif.blocks[tridata_id].radius):
                nif.blocks[tridata_id].radius = r

        # correct scale
        nif.blocks[tridata_id].center.x *= final_scale
        nif.blocks[tridata_id].center.y *= final_scale
        nif.blocks[tridata_id].center.z *= final_scale
        nif.blocks[tridata_id].radius *= final_scale

        materialIndex += 1 # ...and process the next material

    # return updated nif
    return nif



#
# EXPERIMENTAL: Export texture effect.
# 
def export_textureeffect(ob, parent_block_id, parent_scale, nif):
    assert(ob.getType() == 'Empty')
    last_id = nif.header.nblocks - 1
    
    # add a trishape block, and refer to this block in the parent's children list
    texeff_id = last_id + 1
    last_id = texeff_id
    assert(texeff_id == len(nif.blocks)) # debug
    nif.blocks.append(niflib.NiTextureEffect()) # this should be block[texeff_id]
    nif.blocks[texeff_id].block_type.value = 'NiTextureEffect'
    nif.blocks[parent_block_id].child_id.append(texeff_id)
    nif.blocks[parent_block_id].num_children += 1
    nif.blocks[parent_block_id].effect_id.append(texeff_id)
    nif.blocks[parent_block_id].num_effects += 1
    nif.header.nblocks += 1
        
    # fill in the NiTextureEffect's non-trivial values
    nif.blocks[texeff_id].flags = 0x0004
    nif.blocks[texeff_id].translation, \
    nif.blocks[texeff_id].rotation, \
    scale, \
    nif.blocks[texeff_id].velocity \
    = export_matrix(ob, 'none')
    # scale correction
    nif.blocks[texeff_id].translation.x *= parent_scale
    nif.blocks[texeff_id].translation.y *= parent_scale
    nif.blocks[texeff_id].translation.z *= parent_scale
    # ... not sure what scaling does to a texture effect
    nif.blocks[texeff_id].scale = 1.0;
    
    # guessing
    nif.blocks[texeff_id].dunno2[0] = 1.0
    nif.blocks[texeff_id].dunno2[1] = 0.0
    nif.blocks[texeff_id].dunno2[2] = 0.0
    nif.blocks[texeff_id].dunno2[3] = 0.0
    nif.blocks[texeff_id].dunno2[4] = 1.0
    nif.blocks[texeff_id].dunno2[5] = 0.0
    nif.blocks[texeff_id].dunno2[6] = 0.0
    nif.blocks[texeff_id].dunno2[7] = 0.0
    nif.blocks[texeff_id].dunno2[8] = 1.0
    nif.blocks[texeff_id].dunno2[9] = 0.0
    nif.blocks[texeff_id].dunno2[10] = 0.0
    nif.blocks[texeff_id].dunno2[11] = 0.0
    nif.blocks[texeff_id].dunno3 = 2
    nif.blocks[texeff_id].dunno4 = 3
    nif.blocks[texeff_id].dunno5 = 2
    nif.blocks[texeff_id].dunno6 = 2
    nif.blocks[texeff_id].dunno7 = 0
    nif.blocks[texeff_id].dunno8[0] = 1.0
    nif.blocks[texeff_id].dunno8[1] = 0.0
    nif.blocks[texeff_id].dunno8[2] = 0.0
    nif.blocks[texeff_id].dunno8[3] = 0.0
    nif.blocks[texeff_id].ps2_l = 0
    nif.blocks[texeff_id].ps2_k = -75
    nif.blocks[texeff_id].dunno9 = 0

    # add NiTextureEffect's texture source
    nif.blocks[texeff_id].source_id = 91

    texsrc_id = last_id + 1
    last_id = texsrc_id
    assert(texsrc_id == len(nif.blocks)) # debug
    nif.blocks.append(niflib.NiSourceTexture())
    nif.blocks[texsrc_id].block_type.value = 'NiSourceTexture'
    nif.blocks[texeff_id].source_id = texsrc_id
    nif.header.nblocks += 1
            
    nif.blocks[texsrc_id].external = 1
    nif.blocks[texsrc_id].texture_file_name.value = 'enviro 01.TGA' # ?
    nif.blocks[texsrc_id].pixel_layout = 5 # default?
    nif.blocks[texsrc_id].mipmap = 1 # default?
    nif.blocks[texsrc_id].alpha = 3 # default?
    nif.blocks[texsrc_id].dunno1 = 1 # ?

    return nif

# 
# Export all children of blender object ob, already stored in
# nif.blocks[ob_block_id], and return the updated nif.
# 
def export_children(ob, ob_block_id, parent_scale, nif):
    # loop over all ob's children
    for ob_child in Blender.Object.Get():
        if (ob_child.getParent() == ob):
            # we found a child! try to add it to ob's children
            # is it a texture effect node?
            if ((ob_child.getType() == 'Empty') and (ob_child.getName()[:13] == 'TextureEffect')):
                nif = export_textureeffect(ob_child, ob_block_id, parent_scale, nif)
            # is it a regular node?
            elif (ob_child.getType() == 'Mesh') or (ob_child.getType() == 'Empty'):
                nif = export_node(ob_child, 'localspace', ob_block_id, parent_scale, ob_child.getName(), nif)

    # return updated nif
    return nif

#
# Convert an object's transformation matrix to a niflib quadrupple ( translate, rotate, scale, velocity ).
# The scale is a vector; but non-uniform scaling is not supported by the nif format, so for these we'll have to apply the transformation
# when exporting the vertex coordinates... ?
#
def export_matrix(ob, space):
    global epsilon
    nt = niflib.NiVector()
    nr = niflib.NiMatrix()
    ns = niflib.NiVector()
    nv = niflib.NiVector()
    
    # decompose
    bs, br, bt = getObjectSRT(ob, space)
    
    # and fill in the values
    nt.x = bt[0]
    nt.y = bt[1]
    nt.z = bt[2]
    nr.x.x = br[0][0]
    nr.x.y = br[1][0]
    nr.x.z = br[2][0]
    nr.y.x = br[0][1]
    nr.y.y = br[1][1]
    nr.y.z = br[2][1]
    nr.z.x = br[0][2]
    nr.z.y = br[1][2]
    nr.z.z = br[2][2]
    ns.x = bs[0]
    ns.y = bs[1]
    ns.z = bs[2]
    nv.x = 0.0
    nv.y = 0.0
    nv.z = 0.0

    # for now, we don't support non-uniform scaling
    if abs(ns.x - ns.y) + abs(ns.y - ns.z) > epsilon:
        raise NIFExportError('ERROR%t|non-uniformly scaled objects not yet supported; apply size and rotation (CTRL-A in Object Mode) and try again.')

    # return result
    return (nt, nr, ns, nv)



# Find scale, rotation, and translation components of an
# object. Returns a triple (bs, br, bt), where bs is a scale vector,
# br is a 3x3 rotation matrix, and bt is a translation vector. It
# should hold that "ob.getMatrix(space) == bs * br * bt".
def getObjectSRT(ob, space):
    global epsilon
    if (space == 'none'):
        bs = Blender.Mathutils.Vector([1.0, 1.0, 1.0])
        br = Blender.Mathutils.Matrix()
        br.identity()
        bt = Blender.Mathutils.Vector([0.0, 0.0, 0.0])
        return (bs, br, bt)
    assert((space == 'worldspace') or (space == 'localspace'))
    mat = ob.getMatrix('worldspace')
    # localspace bug fix:
    if (space == 'localspace'):
        matparentinv = ob.getParent().getMatrix('worldspace')
        matparentinv.invert()
        mat = mat * matparentinv
    
    # get translation
    bt = mat.translationPart()
    
    # get the rotation part, this is scale * rotation
    bsr = mat.rotationPart()
    
    # get the squared scale matrix
    bsrT = Blender.Mathutils.CopyMat(bsr)
    bsrT.transpose()
    bs2 = bsr * bsrT # bsr * bsrT = bs * br * brT * bsT = bs^2
    # debug: br2's off-diagonal elements must be zero!
    assert(abs(bs2[0][1]) + abs(bs2[0][2]) \
        + abs(bs2[1][0]) + abs(bs2[1][2]) \
        + abs(bs2[2][0]) + abs(bs2[2][1]) < epsilon)
    
    # get scale components
    bs = Blender.Mathutils.Vector(\
         [ sqrt(bs2[0][0]), sqrt(bs2[1][1]), sqrt(bs2[2][2]) ])
    # and fix their sign
    if (bsr.determinant() < 0): bs.negate()
    
    # get the rotation matrix
    br = Blender.Mathutils.Matrix(\
        [ bsr[0][0]/bs[0], bsr[0][1]/bs[0], bsr[0][2]/bs[0] ],\
        [ bsr[1][0]/bs[1], bsr[1][1]/bs[1], bsr[1][2]/bs[1] ],\
        [ bsr[2][0]/bs[2], bsr[2][1]/bs[2], bsr[2][2]/bs[2] ])
    
    # debug: rotation matrix must have determinant 1
    assert(abs(br.determinant() - 1.0) < epsilon)

    # debug: rotation matrix must satisfy orthogonality constraint
    for i in range(3):
        for j in range(3):
            sum = 0.0
            for k in range(3):
                sum += br[k][i] * br[k][j]
            if (i == j): assert(abs(sum - 1.0) < epsilon)
            if (i != j): assert(abs(sum) < epsilon)
    
    # debug: the product of the scaling values must be equal to the determinant of the blender rotation part
    assert(abs(bs[0]*bs[1]*bs[2] - bsr.determinant()) < epsilon)
    
    # TODO: debug: check that indeed bm == bs * br * bt

    return (bs, br, bt)



# calculate distance between two vectors
def get_distance(v, w):
    return sqrt((v[0]-w.x)*(v[0]-w.x) + (v[1]-w.y)*(v[1]-w.y) + (v[2]-w.z)*(v[2]-w.z))



# start blender file selector for export
Blender.Window.FileSelector(export_nif, "Export NIF")
