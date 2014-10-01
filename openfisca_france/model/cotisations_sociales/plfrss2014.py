# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import division

from datetime import date
from functools import partial
import logging
from numpy import maximum as max_, minimum as min_

from openfisca_core.columns import FloatCol
from openfisca_core.enumerations import Enum
import openfisca_france.model.irpp_reductions_impots as ri
from openfisca_core import reforms
from openfisca_core.formulas import build_dated_formula_couple, build_simple_formula_couple
from openfisca_france import entities


log = logging.getLogger(__name__)

CAT = Enum(['prive_non_cadre',
            'prive_cadre',
            'public_titulaire_etat',
            'public_titulaire_militaire',
            'public_titulaire_territoriale',
            'public_titulaire_hospitaliere',
            'public_non_titulaire'])


def _alleg_plfrss2014_prive(salbrut, sal_h_b, type_sal, taille_entreprise, _P):
    '''
    Allègement de cotisations salariées sur les bas et moyens salaires du secteur privé
    '''
    taux = taux_alleg_plfrss2014_prive(sal_h_b, taille_entreprise, _P)
    allegement = taux * salbrut * (
        (type_sal == CAT['prive_non_cadre']) | (type_sal == CAT['prive_cadre'])
        )
    return allegement


def _alleg_plfrss2014_public(salbrut, type_sal, _P):
    '''
    Allègement de cotisations salariées sur les bas et moyens salaires du secteur public
    '''
    taux = taux_alleg_plfrss2014_public(salbrut, _P)
    allegement = taux * salbrut * (
        (type_sal == CAT['public_titulaire_etat'])
        | (type_sal == CAT['public_titulaire_militaire'])
        | (type_sal == CAT['public_titulaire_territoriale'])
        | (type_sal == CAT['public_non_titulaire'])  # TODO: check this category
        )
    return allegement

############################################################################
# # Helper functions
############################################################################


def taux_alleg_plfrss2014_prive(sal_h_b, taille_entreprise, P):
    '''
    Exonération de cotisations des salariés du secteur privé PLFRSS2014
    http://www.assemblee-nationale.fr/14/projets/pl2044-ei.asp#P139_9932
    '''
    # La divison par zéro engendre un warning
    # Le montant maximum de l’allègement dépend de l’effectif de l’entreprise.
    # Le montant est calculé chaque année civile, pour chaque salarié ;
    # il est égal au produit de la totalité de la rémunération annuelle telle
    # que visée à l’article L. 242-1 du code de la Sécurité sociale par un
    # coefficient.
    # Ce montant est majoré de 10 % pour les entreprises de travail temporaire
    # au titre des salariés temporaires pour lesquels elle est tenue à
    # l’obligation d’indemnisation compensatrice de congés payés.

    smic_h_b = P.gen.smic_h_b
    seuil = P.plfrss2014.exonerations_bas_salaires.prive.seuil
    taux = P.plfrss2014.exonerations_bas_salaires.prive.taux
    if seuil <= 1:
        return 0
    return (taux * min_(1, max_(seuil * smic_h_b / (sal_h_b + 1e-10) - 1, 0) / (seuil - 1)))


def taux_alleg_plfrss2014_public(salbrut, P):
    '''
    Exonération cotisations des salariés du secteur public PLFRSS2014
    http://www.assemblee-nationale.fr/14/projets/pl2044-ei.asp#P139_9932
    '''
    parametres = P.plfrss2014.exonerations_bas_salaires.public
    alleg = (parametres.taux_1 * (salbrut <= parametres.seuil_1)
             + parametres.taux_2 * (parametres.seuil_1 < salbrut <= parametres.seuil_2)
             + parametres.taux_10 * (parametres.seuil_2 < salbrut <= parametres.seuil_3)
             + parametres.taux_10 * (parametres.seuil_3 < salbrut <= parametres.seuil_4)
             + parametres.taux_10 * (parametres.seuil_4 < salbrut <= parametres.seuil_5)
             + parametres.taux_10 * (parametres.seuil_5 < salbrut <= parametres.seuil_6)
             + parametres.taux_10 * (parametres.seuil_6 < salbrut <= parametres.seuil_7)
             + parametres.taux_10 * (parametres.seuil_7 < salbrut <= parametres.seuil_8)
             + parametres.taux_10 * (parametres.seuil_8 < salbrut <= parametres.seuil_9)
             + parametres.taux_10 * (parametres.seuil_9 < salbrut <= parametres.seuil_10)
             + parametres.taux_11 * (parametres.seuil_10 < salbrut <= parametres.seuil_11)
             )
    return alleg


def _reduction_impot_exceptionnelle(rfr, nb_adult, nb_par, _P):
    parametres = _P.plfr2014.reduction_impot_exceptionnelle
    plafond = parametres.seuil * nb_adult + (nb_par - nb_adult) * 2 * parametres.majoration_seuil
    montant = parametres.montant_plafond * nb_adult
    return min_(max_(plafond + montant - rfr, 0), montant)


def _reductions_2013(accult, adhcga, cappme, creaen, daepad, deffor, dfppce, doment, domlog, donapd, duflot, ecpess,
                     garext, intagr, invfor, invlst, ip_net, locmeu, mecena, mohist, patnat, prcomp, repsoc, resimm,
                     rsceha, saldom, scelli, sofica, spfcpi, reduction_impot_exceptionnelle):
    '''
    Renvoie la somme des réductions d'impôt à intégrer pour l'année 2013
    '''
    total_reductions = (accult + adhcga + cappme + creaen + daepad + deffor + dfppce + doment + domlog + donapd +
                        duflot + ecpess + garext + intagr + invfor + invlst + locmeu + mecena + mohist + patnat +
                        prcomp + repsoc + resimm + rsceha + saldom + scelli + sofica + spfcpi +
                        reduction_impot_exceptionnelle)
    return min_(ip_net, total_reductions)


def build_entity_class_by_key_plural(TaxBenefitSystem):
    reform_entity_class_by_symbol = reforms.clone_entity_classes(entities.entity_class_by_symbol, symbols = ['foy'])
    class ReformEntities(object):
        entity_class_by_symbol = reform_entity_class_by_symbol

    build_simple_formula_couple(
        name = "reduction_impot_exceptionnelle",
        column = FloatCol(
            entity = 'foy',
            function = _reduction_impot_exceptionnelle,
            label = "Réduction d'impôt exceptionnelle",
            ),
        entities = ReformEntities,
        )
    build_dated_formula_couple(
        name = 'reductions',
        dated_functions = [
            dict(start = date(2002, 1, 1),
                 end = date(2002, 12, 31),
                 function = ri._reductions_2002,
                 ),
            dict(start = date(2003, 1, 1),
                 end = date(2004, 12, 31),
                 function = ri._reductions_2003_2004,
                 ),
            dict(start = date(2005, 1, 1),
                 end = date(2005, 12, 31),
                 function = ri._reductions_2005,
                 ),
            dict(start = date(2006, 1, 1),
                 end = date(2006, 12, 31),
                 function = ri._reductions_2006,
                 ),
            dict(start = date(2007, 1, 1),
                 end = date(2007, 12, 31),
                 function = ri._reductions_2007,
                 ),
            dict(start = date(2008, 1, 1),
                 end = date(2008, 12, 31),
                 function = ri._reductions_2008,
                 ),
            dict(start = date(2009, 1, 1),
                 end = date(2009, 12, 31),
                 function = ri._reductions_2009,
                 ),
            dict(start = date(2010, 1, 1),
                 end = date(2010, 12, 31),
                 function = ri._reductions_2010,
                 ),
            dict(start = date(2011, 1, 1),
                 end = date(2011, 12, 31),
                 function = ri._reductions_2011,
                 ),
            dict(start = date(2012, 1, 1),
                 end = date(2012, 12, 31),
                 function = ri._reductions_2012,
                 ),
            dict(start = date(2013, 1, 1),
                 end = date(2013, 1, 1),
                 function = _reductions_2013,
                 ),
            ],
        column = FloatCol(entity = 'foy'),
        entities = ReformEntities,
        replace = True,
        )

    reform_entity_class_by_key_plural = entities.build_entity_class_by_key_plural(reform_entity_class_by_symbol)
    return reform_entity_class_by_key_plural


dated_legislation_diff = {
    "plfr2014": {
        "@type": "Node",
        "description": "Projet de loi de finance 2014",
        "children": {
            "reduction_impot_exceptionnelle": {
                "@type": "Node",
                "description": "Réduction d'impôt exceptionnelle",
                "children": {
                    "montant_plafond": {
                        "@type": "Parameter",
                        "description": "Montant plafond par part pour les deux premières parts",
                        "format": "integer",
                        "unit": "currency",
                        "value": 350,
                        },
                    "seuil": {
                        "@type": "Parameter",
                        "description": "Seuil (à partir duquel la réduction décroît) par part pour les deux premières parts",
                        "format": "integer",
                        "unit": "currency",
                        "value": 13795,
                        },
                    "majoration_seuil": {
                        "@type": "Parameter",
                        "description": "Majoration du seuil par demi-part supplémentaire",
                        "format": "integer",
                        "unit": "currency",
                        "value": 3536,
                        },
                    },
                },
            },
        },
    "plfrss2014": {
        "@type": "Node",
        "description": "Projet de loi de financement de la sécurité sociale rectificative 2014",
        "children": {
            "exonerations_bas_salaires": {
                "@type": "Node",
                "description": "Exonérations de cotiastions salariées sur les bas salaires",
                "children": {
                    "prive": {
                        "@type": "Node",
                        "description": "Salariés du secteur privé",
                        "children": {
                            "taux": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.03,
                                },
                            "seuil": {
                                "@type": "Parameter",
                                "description": "Seuil (en SMIC)",
                                "format": "rate",
                                "value": 1.3,
                                },
                            },
                        },
                    "public": {
                        "@type": "Node",
                        "description": "Salariés du secteur public",
                        "children": {
                            "taux_1": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.02,
                                },
                            "seuil_1": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 312,
                                },
                            "taux_2": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.018,
                                },
                            "seuil_2": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 328,
                                },
                            "taux_3": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.016,
                                },
                            "seuil_3": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 343,
                                },
                            "taux_4": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.014,
                                },
                            "seuil_4": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 359,
                                },
                            "taux_5": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.012,
                                },
                            "seuil_5": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 375,
                                },
                            "taux_6": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.01,
                                },
                            "seuil_6": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 390,
                                },
                            "taux_7": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.008,
                                },
                            "seuil_7": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 406,
                                },
                            "taux_8": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.007,
                                },
                            "seuil_8": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 421,
                                },
                            "taux_9": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.006,
                                },
                            "seuil_9": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 437,
                                },
                            "taux_10": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.005,
                                },
                            "seuil_10": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 453,
                                },
                            "taux_11": {
                                "@type": "Parameter",
                                "description": "Taux",
                                "format": "rate",
                                "value": 0.002,
                                },
                            "seuil_11": {
                                "@type": "Parameter",
                                "description": "Indice majoré plafond",
                                "format": "integer",
                                "value": 468,
                                },
                            },
                        },
                    },
                },
            },
        },
    }
