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


import copy
import datetime


from openfisca_core import legislations
from openfisca_core.reforms import Reform
from openfisca_france.model.cotisations_sociales import plfrss2014
import openfisca_france


TaxBenefitSystem = openfisca_france.init_country()
tax_benefit_system = TaxBenefitSystem()


def test_systemic_reform(year = 2013):
    scenario = tax_benefit_system.new_scenario().init_single_entity(
        axes = [
            dict(
                count = 10,
                max = 13795*(1+.1)*(1+.03),
                min = 13795*(1+.1)*(1-.03),
                name = 'sali',
                ),
            ],
        date = datetime.date(year, 1, 1),
        parent1 = dict(birth = datetime.date(year - 40, 1, 1)),
        )

    reference_dated_legislation_json = legislations.generate_dated_legislation_json(
        tax_benefit_system.legislation_json,
        datetime.date(year, 1, 1)
        )
    reform_dated_legislation_json = copy.deepcopy(reference_dated_legislation_json)
    for key, key_parameters in plfrss2014.dated_legislation_diff.iteritems():
        reform_dated_legislation_json["children"][key] = key_parameters

    entity_class_by_key_plural = plfrss2014.build_entity_class_by_key_plural(TaxBenefitSystem)

    reform = Reform(
        dated_legislation_json = reform_dated_legislation_json,
        entity_class_by_key_plural = entity_class_by_key_plural,
        name = u"PLFR2014",
        reference_dated_legislation_json = reference_dated_legislation_json,
        )

    simulation = scenario.new_simulation(debug = True)
    rfr = simulation.calculate('rfr')
    impo = simulation.calculate('impo')
    print(rfr)
    print(impo)
    print('-' * 20)
    scenario.add_reform(reform)
    reform_simulation = scenario.new_simulation(debug = True, reform_name = reform.name)
    reform_reduction_impot_exceptionnelle = reform_simulation.calculate('reduction_impot_exceptionnelle')
    print(reform_reduction_impot_exceptionnelle)
    reform_rfr = reform_simulation.calculate('rfr')
    reform_impo = reform_simulation.calculate('impo')
    print(reform_rfr)
    print(reform_impo)


if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(level = logging.ERROR, stream = sys.stdout)
    test_systemic_reform()
