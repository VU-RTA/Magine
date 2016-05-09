# -*- coding: utf-8 -*-
import cPickle as pickle
import os
from bioservices import UniProt, KEGG, UniChem, HGNC, PathwayCommons, EUtils
import networkx as nx
try:
    uniprot.get('TP53')
except:
    uniprot = UniProt()
    uniprot.TIMEOUT = 100
try:
    kegg.get('hsa:219')
except:
    kegg = KEGG()
    kegg.TIMEOUT = 100

hugo = HGNC()
chem = UniChem()

#TODO create a database to store all of this
#TODO create a kegg to uniprot identifier dictionary
directory = os.path.dirname(__file__)
# mouse genes
mouse_kegg_to_uniprot = pickle.load(open(os.path.join(directory, 'mouse_kegg_mapper.p'), 'rb'))
mouse_uniprot_to_gene_name = pickle.load(open(os.path.join(directory, 'mouse_uniprot_to_gene_mapper.p'), 'rb'))
# human genes
human_uniprot_to_gene_name = pickle.load(open(os.path.join(directory, 'network_based_UPids_to_genes.p'), 'rb'))
human_uniprot_to_gene_name_2 = pickle.load(open(os.path.join(directory, 'kegg_to_uniprot_gene_name.p'), 'rb'))
human_kegg_to_uniprot = pickle.load(open(os.path.join(directory, 'human_kegg_mapper.p'), 'rb'))
# chemical conversions
hmdb_to_kegg_improved = pickle.load(open(os.path.join(directory, 'hmdb_to_kegg_from_hmdb.p'), 'rb'))
kegg_to_hmdb_improved = pickle.load(open(os.path.join(directory, 'kegg_to_hmdb_from_hmdb.p'), 'rb'))
kegg_to_hmdb = pickle.load(open(os.path.join(directory, 'kegg_to_hmdb.p'),'rb'))
kegg_hmdb_to_name = pickle.load(open(os.path.join(directory,"kegg_to_chemical_name_from_hmdb.p"), "rb"))
# creation of a manual dictionary because of kegg to uniprot errors.
# These errors are mostly on KEGG sides that link it to an unreviewed Uniprot ID
manual_dict = {'hsa:857': 'CAV1',
               'hsa:2250': 'FGF5',
               'hsa:5337': 'PLD1',
               'hsa:4312': 'MMP1',
               'hsa:102723407': 'IGHV4OR15-8',
               'hsa:100132074': 'FOXO6',
               'hsa:728635': 'DHRS4L1',
               'hsa:10411': 'RAPGEF3'
               }

compound_manual ={'cpd:C07909': 'HMDB15015',
                  }


def create_gene_dictionaries(network,species='hsa'):
    """
    maps network from kegg to gene names
    :param network:
    :param species:
    """

    # first we will check the pre-created dictionaries
    if species == 'hsa':
        dictionary = human_kegg_to_uniprot
    elif species == 'mmu':
        dictionary = mouse_kegg_to_uniprot
    # Create the dictionary to store all conversions to be returned
    kegg_to_gene_name = {}
    # List to store things not in the initial dictionary
    unknown_genes = []
    nodes = network.nodes()
    # check stores dictionaries
    for i in nodes:
        if str(i).startswith(species):
            network.node[i]['keggName'] = i
            if i in dictionary:
                kegg_to_gene_name[i] = dictionary[i]
            elif i in manual_dict:
                kegg_to_gene_name[i] = manual_dict[i]
            else:
                if str(i).startswith(species):
                    unknown_genes.append(i)
    if len(unknown_genes) == 0:
        return kegg_to_gene_name
    # create string to call uniprot for mapping
    search_string = ''
    for n, i in enumerate(unknown_genes):
        search_string += str(i) + '\t'
    search_string = search_string.rstrip('\t')
    # This is where it gets tricky. Checking to see if there is a uniprot mapping for the species, if not, trying
    # from KEGG side. Sometimes kegg links to a different uniprot, or uniprot links to a different kegg. Annoying
    uni_dict = dict(uniprot.mapping("KEGG_ID", "GENENAME", query=search_string))
    for i in unknown_genes:
        if i in uni_dict:
            kegg_to_gene_name[uni_dict[i][0]] = i
        else:
            uniprot_tmp = kegg.conv("uniprot", i)
            if uniprot_tmp == '\n':
                continue
            if type(uniprot_tmp) == int:
                continue
            if len(uniprot_tmp) > 0:
                uniprot_tmp = str(dict(uniprot_tmp)[i].lstrip('up:'))
            else:
                continue
            tmp_dict = dict(uniprot.mapping(fr="ACC", to="GENENAME", query=[uniprot_tmp+'\t']))
            if uniprot_tmp in tmp_dict:
                kegg_to_gene_name[i] = tmp_dict[uniprot_tmp][0]
            else:
                print("Who the fuck knows then...", i)
    return kegg_to_gene_name


def hugo_mapper(network, species='hsa'):
    """ Converts all MIR from kegg

    :param network:
    :return:

    """
    nodes = network.nodes()
    hugo_dict = {}
    for i in nodes:
        if str(i).startswith(species):
            out = hugo.fetch("entrez_id",i.lstrip('hsa:'),frmt='json')
            if 'response' in out:
                if 'docs' in out['response']:
                    if len(out['response']['docs'])>0:
                        if 'symbol' in out['response']['docs'][0]:
                            hugo_dict[i] = out['response']['docs'][0]['symbol']
    return hugo_dict


def create_compound_dictionary(network):
    """ Maps network from kegg to gene names

    :param network:
    :return: dictionary

    """
    cpd_to_hmdb = {} # he
    still_unknown = []
    nodes = network.nodes()
    for i in nodes:
        if i.startswith('cpd:'):
            network.node[i]['keggName'] = i
            if i.lstrip('cpd:') in kegg_to_hmdb_improved:
                mapping = kegg_to_hmdb_improved[i.lstrip('cpd:')]
                if type(mapping) == list:
                    hmdb_options = mapping[0]
                    if len(mapping) == 1:
                        cpd_to_hmdb[i] = mapping[0]
                    else:
                        cpd_to_hmdb[i] = mapping[0]
                        for j in range(1, len(mapping)):
                            hmdb_options += "_%s" % mapping[j]
                    network.node[i]['hmdbNames'] = hmdb_options
                    if i.lstrip('cpd:') in kegg_hmdb_to_name:
                        network.node[i]['chemName'] = kegg_hmdb_to_name[i.lstrip('cpd:')]
                else:
                    print('Did not return a list...')

            else:
                still_unknown.append(i)
    if len(still_unknown) == 0:
        return cpd_to_hmdb
    kegg_hmdb = chem.get_mapping("kegg_ligand", "hmdb")
    for i in still_unknown:
        if i.lstrip('cpd') in kegg_hmdb:
            cpd_to_hmdb[i] = kegg_to_hmdb[i.lstrip('cpd:')][0]
        else:
            print("Cannot find a HMDB mapping for %s " % i)
    return cpd_to_hmdb


def convert_all(network,species='hsa'):
    """ Maps gene names to HGNC and kegg compound to HMDB

    :param network:
    :param species:
    :return:
    """
    renamed_network = nx.relabel_nodes(network, compound_manual)
    print('Started converting kegg compounds to HMDB')
    dict1 = create_compound_dictionary(renamed_network)
    renamed_network = nx.relabel_nodes(renamed_network, dict1)
    print('Started converting kegg genes to HGNC')
    dict2 = create_gene_dictionaries(renamed_network, species=species)
    renamed_network = nx.relabel_nodes(renamed_network, dict2)
    print('Started to check for miRNAs')
    dict3 = hugo_mapper(renamed_network,species=species)
    renamed_network = nx.relabel_nodes(renamed_network, dict3)

    return renamed_network
