import numpy as np

#from chatgpt
def normalize_vector(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm

#from chatgpt
def calculate_rotation_axis(v1, v2):
    v1_normalized = normalize_vector(v1)
    v2_normalized = normalize_vector(v2)
    axis = np.cross(v1_normalized, v2_normalized)
    return normalize_vector(axis)

#from chatgpt
def calculate_rotation_angle(v1, v2):
    v1_normalized = normalize_vector(v1)
    v2_normalized = normalize_vector(v2)
    dot_product = np.dot(v1_normalized, v2_normalized)
    return np.arccos(dot_product)

#from chatgpt
def create_rotation_matrix(axis, angle):
    c = np.cos(angle)
    s = np.sin(angle)
    t = 1 - c
    x, y, z = axis
    return np.array([
        [t * x**2 + c, t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y**2 + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z**2 + c]
    ])

#from chatgpt
def rotate_vector(vector, rotation_matrix):
    return np.dot(rotation_matrix, vector)


def calculate_virtual_center(resn,N,CA,CB):
    """
    From Foldseek supplementary:
    3Di virtual center. During the transformation of structures into 3Di
    sequences, the virtual centers of residues are used to determine interacting residues. The optimized virtual
    center lies on the plane defined by the atoms N, Cα, and Cβ. Moreover, Cβ, Cα, and the virtual center form
    an angle of 90◦. The distance between the virtual center and Cα equals twice the distance between Cβ and
    Cα. For glycines, the Cβ is approximated by assuming that the Cβ, Cbackbone, and N atoms are arranged at
    the vertices of a regular tetrahedron with Cα at its centroid, and a centroid to vertex distance of 1.5336 Å.

    """
    A1 = CB-CA
    A2 = N-CA
    d = np.linalg.norm(A1)
    if resn == "GLY":
        d = 1.5336
        axis = calculate_rotation_axis(A1,A2)
        angle = calculate_rotation_angle(A1,A2)
        middle_vector = rotate_vector(A1,create_rotation_matrix(axis,angle/2))
        angle = np.arccos(-1/3)
        A1_adjusted = rotate_vector(middle_vector,create_rotation_matrix(axis,-angle/2))
        A2_adjusted = rotate_vector(middle_vector,create_rotation_matrix(axis,angle/2))
        angle = np.pi*(2/3)
        A1 = normalize_vector(rotate_vector(A1_adjusted,create_rotation_matrix(normalize_vector(A2_adjusted),angle)))*d
    if resn != None:
        axis = calculate_rotation_axis(A1,A2)
        angle = -np.pi/2
        virtual_center = normalize_vector(rotate_vector(A1,create_rotation_matrix(axis,angle)))
        

    return virtual_center*2*d + CA





def foldseek_virtual_center(model,model_CA):
    max_resi = int(np.max(np.array([int(x.resi) for x in model_CA.atom])))
    resi = 0
    CB = None
    
    for atom in model.atom:
        if int(atom.resi) <= max_resi and atom.chain == "A":
            if int(atom.resi) != resi:
                resi = int(atom.resi)
                if resi == 2:
                    virtual_centers = calculate_virtual_center(resn,N,CA,CB)
                elif resi > 2:
                    virtual_centers = np.vstack((virtual_centers,calculate_virtual_center(resn,N,CA,CB)))
                    # print(int(resi))
                    # if int(resi) == 2:
                    #     virtual_centers = calculate_virtual_center(resn,N,CA,CB)
                    # else:
                    #     np.vstack((virtual_centers,calculate_virtual_center(resn,N,CA,CB)))                  
                resn = atom.resn
            if atom.name == "N":
                N = np.array(atom.coord)
            elif atom.name == "CA":
                CA = np.array(atom.coord)
            elif atom.name == "CB" or (atom.name == "C" and resn == "GLY"):
                CB = np.array(atom.coord)
    virtual_centers = np.vstack((virtual_centers,calculate_virtual_center(resn,N,CA,CB)))
    return virtual_centers


def add_space(number,max_length,decimaler):
    number = str(number)
    if len(number.split(".")) > 1:
        while len(number.split(".")[-1]) != decimaler:
            number += "0"
    space = " "
    for x in range(int(max_length-len(str(number)))):
        space += " "
    return space + str(number)

from pymol import cmd

def virtual_center_to_pdb(virtual_centers,outfilename,structure_name):
    model = cmd.get_model(structure_name+" and name CA and chain A and not HETATM").atom
    with open(outfilename,"w") as out:
        out.write("MODEL\t1\n")
        for i,v in enumerate(virtual_centers):
            resi = str(i+1)
            resi = add_space(resi,6,0)
            v0 = add_space(round(v[0],3),7,3)
            v1 = add_space(round(v[1],3),7,3)
            v2 = add_space(round(v[2],3),7,3)
            out.write(f"ATOM{resi}  CA  {model[i].resn} A{resi[3:]}    {v0}{v1}{v2}\t1.00 98.00           C\n")

from scipy.spatial import cKDTree

def run(score_list,structure_list,minmax,max_dist):
    """
    
    """

    hotspot_list = []
    for i, score in enumerate(score_list):
        middle_s = {}
        model = cmd.get_model(structure_list[i])
        model_CA = cmd.get_model(structure_list[i]+" and name CA and chain A and not HETATM")
        vc_list = foldseek_virtual_center(model,model_CA)
        for j, s in enumerate(score):
            if s > minmax[0] and s < minmax[1]:
                hashable_list = ",".join([str(x) for x in vc_list[j,:]])
                middle_s[hashable_list] = j
        print(middle_s)
        kd = cKDTree([[float(y) for y in x.split(",")] for x in middle_s.keys()])
        closest_to_ref = {}
        ref_is_closest = {}
        for vc, index in middle_s.items():
            query = kd.query([float(x) for x in vc.split(",")],k=2)
            dist = query[0][1]
            idx = query[1][1]
            if dist < max_dist:
                closest_to_ref[index] = idx
                if idx in ref_is_closest.keys():
                    ref_is_closest[idx].add(index)
                else:
                    ref_is_closest[idx] = {index}
        hotspot = []
        used_aa = set()
        print(len(closest_to_ref),closest_to_ref)
        print(len(ref_is_closest),ref_is_closest)
        for index in closest_to_ref.keys():
            if index not in used_aa:
                h = {index}
                add = set()
                while True:
                    for ele in h:
                        if ele not in used_aa:
                            add.add(closest_to_ref[ele])
                            if ele in ref_is_closest:
                                add = add.union(ref_is_closest[ele])
                    if add == set():
                        break
                    print(add)
                    used_aa = used_aa.union(h)
                    h = h.union(add)
                    
                    print(h)
                    print(used_aa)
                    add = set()
                    print(add)
                if len(h) > 1:
                    hotspot.append(h)
        hotspot_list.append(hotspot)
    return hotspot_list
