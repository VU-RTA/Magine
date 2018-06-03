try:
    import cPickle as pickle
except ImportError:  # python3 doesnt have cPickle
    import pickle
import gzip
import os

import pandas as pd

from magine.data.storage import id_mapping_dir
from magine.mappings.databases import download_hgnc, download_ncbi, \
    download_uniprot

pd.set_option('display.width', 20000)


class GeneMapper(object):
    """
    Mapping class between common gene ids

    Database was creating by pulling down everything from HMDB

    Attributes
    ----------
    gene_name_to_uniprot : dict
    gene_name_to_alias_name : dict
    gene_name_to_ensembl : dict
    gene_name_to_kegg : dict

    kegg_to_gene_name : dict
    kegg_to_uniprot : dict

    ncbi_to_symbol : dict

    protein_name_to_gene_name : dict
    protein_name_to_uniprot : dict

    uniprot_to_gene_name : dict
    uniprot_to_kegg : dict

    """
    ncbi_valid_categories = ['GeneID', 'Symbol', 'description']

    hgnc_valid_categories = ['symbol', 'uniprot_ids', 'ensembl_gene_id',
                             'name',
                             'location', 'entrez_id', 'ucsc_id', 'vega_id',
                             'alias_name', 'alias_symbol', 'status',
                             'gene_family', 'gene_family_id', 'ena', 'iuphar',
                             'cd', 'refseq_accession', 'ccds_id', 'pubmed_id',
                             'mgd_id', 'rgd_id', 'lsdb', 'bioparadigms_slc',
                             'enzyme_id', 'merops', 'horde_id',
                             'pseudogene.org', 'cosmic', 'rna_central_ids',
                             'omim_id', 'imgt', 'intermediate_filament_db',
                             ]

    valid_uniprot_cols = ['uniprot', 'Allergome', 'BioCyc', 'BioGrid',
                          'BioMuta', 'CCDS', 'CRC64', 'ChEMBL', 'ChiTaRS',
                          'CleanEx', 'DIP', 'DMDM', 'DNASU', 'DisProt',
                          'DrugBank', 'EMBL', 'EMBL-CDS', 'ESTHER', 'Ensembl',
                          'Ensembl_PRO', 'Ensembl_TRS', 'GI', 'GeneCards',
                          'GeneDB', 'GeneID', 'GeneReviews', 'GeneTree',
                          'GeneWiki', 'Gene_Name', 'Gene_ORFName',
                          'Gene_Synonym', 'GenomeRNAi', 'GuidetoPHARMACOLOGY',
                          'H-InvDB', 'HGNC', 'HOGENOM', 'HOVERGEN', 'HPA',
                          'KEGG', 'KO', 'MEROPS', 'MIM', 'MINT', 'NCBI_TaxID',
                          'OMA', 'Orphanet', 'OrthoDB', 'PATRIC', 'PDB',
                          'PeroxiBase', 'PharmGKB', 'REBASE', 'Reactome',
                          'RefSeq', 'RefSeq_NT', 'STRING', 'SwissLipids',
                          'TCDB', 'TreeFam', 'UCSC', 'UniGene', 'UniParc',
                          'UniPathway', 'UniProtKB-ID', 'UniRef100',
                          'UniRef50',
                          'UniRef90', 'eggNOG', 'neXtProt']

    def __init__(self, species='hsa'):
        self.species = species
        self._reload_fname = os.path.join(id_mapping_dir,
                                          'gene_mapping_instance.p.gz')

        # All are empty until set in load or reload
        self.hgnc = None
        self.ncbi = None
        self.uniprot = None
        self.gene_name_to_uniprot = {}
        self.gene_name_to_alias_name = {}
        self.gene_name_to_ensembl = {}
        self.gene_name_to_kegg = {}
        self.uniprot_to_gene_name = {}
        self.uniprot_to_kegg = {}
        self.protein_name_to_gene_name = {}
        self.protein_name_to_uniprot = {}
        self.kegg_to_gene_name = {}
        self.kegg_to_uniprot = {}
        self.ncbi_to_symbol = {}

        try:
            self.reload()
            print('Loading class data')
        except:
            print('Initializing Gene mapping')
            self.load()

    # @profile
    def load(self):
        hgnc_name = os.path.join(id_mapping_dir, 'hgnc.gz')
        if not os.path.exists(hgnc_name):
            self.hgnc = download_hgnc()
            assert os.path.exists(hgnc_name)
        else:
            self.hgnc = pd.read_csv(hgnc_name, low_memory=False)

        self.hgnc = self.hgnc[self.hgnc['status'] == 'Approved']

        ncbi_name = os.path.join(id_mapping_dir, 'ncbi.gz')
        if not os.path.exists(ncbi_name):
            self.ncbi = download_ncbi()
            assert os.path.exists(ncbi_name)
        else:
            self.ncbi = pd.read_csv(ncbi_name, low_memory=False)

        # gather data from uniprot
        uniprot_path = os.path.join(id_mapping_dir, 'human_uniprot.csv.gz')
        if not os.path.exists(uniprot_path):
            self.uniprot = download_uniprot()
            assert os.path.exists(uniprot_path)
        else:
            self.uniprot = pd.read_csv(uniprot_path, low_memory=False)
        # HGNC
        self.gene_name_to_uniprot = _dict(self.hgnc, 'symbol', 'uniprot_ids')
        self.gene_name_to_alias_name = _dict(self.hgnc, 'symbol', 'alias_name')
        self.gene_name_to_ensembl = _dict(self.hgnc, 'symbol',
                                          'ensembl_gene_id')
        self.uniprot_to_gene_name = _dict(self.hgnc, 'uniprot_ids', 'symbol')

        # uniprot
        self.gene_name_to_kegg = _dict(self.uniprot, 'Gene_Name', 'KEGG')
        self.uniprot_to_kegg = _dict(self.uniprot, 'uniprot', 'KEGG')
        self.kegg_to_gene_name = _dict(self.uniprot, 'KEGG', 'Gene_Name')
        self.kegg_to_uniprot = _dict(self.uniprot, 'KEGG', 'uniprot')

        self.protein_name_to_gene_name = None
        self.protein_name_to_uniprot = None

        self.ncbi_to_symbol = _dict(self.ncbi, 'GeneID', 'Symbol')
        self.save()

    def save(self):
        """ save class instance
        """
        print('Saving class data')
        with gzip.open(self._reload_fname, 'wb') as f:
            f.write(pickle.dumps(self.__dict__))

    def reload(self):
        """ loads class instance
        """

        with gzip.open(self._reload_fname, 'rb') as f:
            data = f.read()
            f.close()
        self.__dict__ = pickle.loads(data)
        
    def check_synonym_dict(self, term, format_name):
        """ checks hmdb database for synonyms and returns formatted name

        Parameters
        ----------
        term : str
        format_name : str

        Returns
        -------
        dict

        """
        synonyms = self.hgnc.copy()
        synonyms = synonyms[~synonyms['alias_symbol'].isna()]
        synonyms['alias_symbol'] = synonyms['alias_symbol'].str.upper()

        hits = synonyms[synonyms['alias_symbol'].str.contains(term.upper())].copy()
        hits['alias_symbol'] = hits['alias_symbol'].str.split('|')

        for i, row in hits.iterrows():
            if term in row['alias_symbol']:
                return [row[format_name]]
        matches = sorted(set(hits[format_name].values))
        return matches


def _dict(data, key, value):
    """
    creates a dictionary with a list of values for each key

    Parameters
    ----------
    data : pandas.DataFrame
    key : str
    value : str

    Returns
    -------

    """
    return_dict = {}

    d = data[[key, value]].copy()
    d.dropna(how='any', inplace=True)

    for i, j in d.values:
        if i in return_dict:
            return_dict[i].append(j)
        else:
            return_dict[i] = [j]
    return return_dict


if __name__ == '__main__':
    gm = GeneMapper()
    gm.load()
    # print(gm.ncbi_to_symbol)
