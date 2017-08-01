import os
from collections import defaultdict

import requests
import pandas as pd

from statsmodels.sandbox.stats.multicomp import fdrcorrection0
from statsmodels.stats.proportion import binom_test

from magine.data.storage import id_mapping_dir
from magine.data.storage import network_data_dir

try:
    import cPickle as pickle
except:
    import pickle


class MagineGO(object):
    def __init__(self, species='hsa'):
        dirname = network_data_dir
        gene_to_go_name = os.path.join(dirname,
                                       '{}_gene_to_go.p'.format(species))
        go_to_gene_name = os.path.join(dirname,
                                       '{}_goids_to_genes.p'.format(species))
        go_to_go_name = os.path.join(dirname,
                                     '{}_goids_to_goname.p'.format(species))
        go_depth = os.path.join(dirname, '{}_godepth.p'.format(species))
        go_aspect = os.path.join(dirname, '{}_go_aspect.p'.format(species))
        for i in [gene_to_go_name, go_to_gene_name, go_to_go_name, go_depth,
                  go_aspect]:
            if not os.path.exists(i):
                download_and_process_go(species=species)

        self.gene_to_go = pickle.load(open(gene_to_go_name, 'rb'))
        self.go_to_gene = pickle.load(open(go_to_gene_name, 'rb'))
        self.go_to_name = pickle.load(open(go_to_go_name, 'rb'))
        self.go_depth = pickle.load(open(go_depth, 'rb'))
        self.go_aspect = pickle.load(open(go_aspect, 'rb'))

    def calculate_enrichment(self, genes, reference=None, evidence_codes=None,
                             aspect=None, use_fdr=True):
        """
    
        Parameters
        ----------
        genes : list
            list of genes
        reference : list
            reference list of species to calculate enrichment
        evidence_codes : list
            GO evidence codes
        use_fdr : bool
            Correct for multiple hypothesis testing
    
        Returns
        -------
    
        """

        # TODO check for alias for genes
        genes = set(genes)
        # TODO add aspects
        term_reference = self.go_to_gene.keys()
        aspect_dict = {
            'P': 'biological_process',
            'C': 'cellular_component',
            'F': 'molecular_function'
        }
        if aspect is None:
            term_reference = self.go_to_gene
            gene_reference = self.gene_to_go
        else:
            term_reference = dict()
            gene_reference = dict()

        if aspect is not None:
            for i in aspect:
                if i not in ['P', 'C', 'F']:
                    print("Error: Aspects are only 'P', 'C', and 'F' \n")
                    quit()
            for i in ['P', 'C', 'F']:
                if i in aspect:
                    term_reference = None

        # TODO add reference
        if reference:
            # TODO check for reference alias
            reference = set(reference)
            reference.intersection_update(set(self.gene_to_go.keys()))
        else:
            reference = set(self.gene_to_go.keys())

        # TODO add evidence_codes

        terms = set()
        for i in genes:
            if i in self.gene_to_go:
                for t in self.gene_to_go[i]:
                    terms.add(t)

        n_genes = len(genes)
        n_ref = float(len(reference))
        res = {}
        for term in terms:

            all_annotated_genes = set(self.go_to_gene[term])
            mapped_genes = genes.intersection(all_annotated_genes)
            n_mapped_genes = len(mapped_genes)

            if n_ref > len(all_annotated_genes):
                mapped_reference_genes = \
                    reference.intersection(all_annotated_genes)
            else:
                mapped_reference_genes = \
                    all_annotated_genes.intersection(reference)

            n_mapped_ref = len(mapped_reference_genes)

            prob = float(n_mapped_ref) / n_ref

            p_value = binom_test(n_mapped_genes, n_genes, prob, 'larger')

            res[term] = ([i for i in mapped_genes], p_value, n_mapped_ref)
        if use_fdr:
            res = sorted(res.items(), key=lambda x: x[1][1])
            fdr = fdrcorrection0([p for _, (_, p, _) in res], is_sorted=True)
            values = fdr[1]
            res = dict([(index, (genes, p, ref))
                        for (index, (genes, _, ref)), p in zip(res, values)])
        return res


def download_and_process_go(species='hsa'):
    print("Creating GO files")
    from goatools import obo_parser
    obo_file = os.path.join(id_mapping_dir, 'go.obo')
    if not os.path.exists(obo_file):
        download_current_go()
    go = obo_parser.GODag(obo_file)
    gene_to_go, go_to_gene, goid_to_name = download_ncbi_gene_file()

    go_aspect = dict()
    go_depth = dict()

    dirname = network_data_dir

    go_to_gene_name = os.path.join(dirname,
                                   '{}_goids_to_genes.p'.format(species))
    go_to_go_name = os.path.join(dirname,
                                 '{}_goids_to_goname.p'.format(species))
    gene_to_go_name = os.path.join(dirname, '{}_gene_to_go.p'.format(species))
    go_depth_name = os.path.join(dirname, '{}_godepth.p'.format(species))
    go_aspect_name = os.path.join(dirname, '{}_go_aspect.p'.format(species))
    for i in go_to_gene.keys():
        go_depth[i] = go[i].depth
        go_aspect[i] = go[i].namespace

    pickle.dump(go_to_gene, open(go_to_gene_name, 'wb'))
    pickle.dump(goid_to_name, open(go_to_go_name, 'wb'))
    pickle.dump(go_depth, open(go_depth_name, 'wb'))
    pickle.dump(go_aspect, open(go_aspect_name, 'wb'))

    for i in go_to_gene:
        term = i
        genes = go_to_gene[i]
        for g in genes:
            if g in gene_to_go:
                gene_to_go[g].add(term)
            else:
                gene_to_go[g] = set()
                gene_to_go[g].add(term)
    pickle.dump(gene_to_go, open(gene_to_go_name, 'wb'))
    print("Done creating GO files")


def download_ncbi_gene_file(tax_ids=None):
    """ Downloads gene2go associations files from ncbi

    Parameters
    ----------
    tax_ids : list
        list of tax ids to consider, default [9606], human
    force_dnld

    Returns
    -------

    """

    from magine.mappings.gene_mapper import GeneMapper
    gm = GeneMapper()

    gene2go_url = "ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz"
    print("Downloading gene2go assocations file")
    r = pd.read_table(gene2go_url, compression='gzip')

    id2gos = defaultdict(set)
    go2term = dict()
    go2genes = defaultdict(set)

    if tax_ids is None:  # Default taxid is Human
        tax_ids = {9606}
    table = r.as_matrix()
    for line in table:
        t_id, gene_id, go_id, evidence, qual, go_term = line[:6]

        t_id = int(t_id)
        if t_id in tax_ids and qual != 'NOT' and evidence != 'ND':
            gene_id = int(gene_id)
            symbol = gm.ncbi_to_symbol[gene_id]
            if len(symbol) == 1:
                symbol = symbol[0]
            else:
                print(symbol)
            go2genes[go_id].add(symbol)
            id2gos[symbol].add(go_id)
            go2term[go_id] = go_term

    return id2gos, go2genes, go2term


def download_current_go(redownload=True):
    go_url = 'http://purl.obolibrary.org/obo/go.obo'
    target_file = 'go.obo'
    out_path = os.path.join(id_mapping_dir, target_file)
    if not os.path.exists(out_path) or redownload:
        print("GO exists, default behavior is to re-download.")

        r = requests.get(go_url, stream=True)
        response = requests.head(go_url)
        print(response.headers)
        # file_size = int(response.headers['content-length'])
        print("Downloading ontology file")
        file_size_dl = 0
        block_sz = 1024
        # block_sz = 8024

        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=block_sz):
                file_size_dl += len(chunk)

                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        print("Downloaded {} and stored {}".format(go_url, out_path))


if __name__ == '__main__':
    # create_annotations()
    download_and_process_go()
    go = MagineGO('hsa')
    terms = go.calculate_enrichment(['BAX'],
                                    reference=['BAX', "LL", 'BCL2', 'CASP1'])
    #    'GO:0001569', (['BAX'], 0.78977569118414181, 1))
    for t in terms:
        print(t, terms[t])
