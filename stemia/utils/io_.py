def read_mrc(path):
    import mrcfile
    with mrcfile.open(path) as mrc:
        return mrc.data.copy(), mrc.header


def write_mrc(data, path, overwrite=False, from_header=None):
    import mrcfile
    with mrcfile.new(path, data, overwrite=overwrite) as mrc:
        if from_header is not None:
            mrc.header.cella = from_header.cella


def read_particle_star(path):
    import pandas as pd
    import starfile
    dct = starfile.read(path)
    if isinstance(dct, pd.DataFrame):
        df = dct
        optics = None
    else:
        df = dct['particles']
        optics = dct['optics']
    return df, optics


def write_particle_star(data, path, overwrite=False, optics=None):
    import starfile
    if optics is not None:
        data = {'optics': optics, 'particles': data}
    starfile.write(data, path, overwrite=overwrite)


def parse_xml(node):
    """
    recursively parse an xml document node from a Warp file
    return a nested dictionary containing the node data
    """
    import numpy as np
    # node type 9 is the document node, we immediately dive deeper
    if node.nodeType == 9:
        return parse_xml(node.firstChild)

    node_name = node.localName
    node_content = {}

    if node.attributes:
        # Param nodes separate their key/value pairs as
        # different attribute tuples
        if node_name == 'Param':
            key, value = node.attributes.items()
            node_name = key[1]
            node_content = value[1]
        # Node nodes contain a xyz tuple and a value
        elif node_name == 'Node':
            x, y, z, value = node.attributes.items()
            node_name = (x[1], y[1], z[1])
            node_content = value[1]
        # everything else contains normal key/value pairs
        else:
            for attr, value in node.attributes.items():
                node_content[attr] = value
    # recursively call this function on child nodes and
    # update this node's dictionary
    if node.childNodes:
        for child in node.childNodes:
            node_content.update(parse_xml(child))
    # text nodes (type 3)
    if node.nodeType == 3:
        text = node.data.strip()
        # ignore empty text
        if not text:
            return {}
        # parse text that contains data points into np.arrays
        points = np.asarray([p.split('|') for p in text.split(';')],
                            dtype=np.float)
        node_content = points

    return {node_name: node_content}


def xml2dict(xml_path):
    """
    parse an xml metadata file of a Warp tilt-series image
    return a dictionary containing the metadata
    """
    from xml.dom.minidom import parse
    document = parse(xml_path)
    return parse_xml(document)
