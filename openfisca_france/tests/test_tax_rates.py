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


from openfisca_core import periods
from openfisca_core.simulations import average_tax_rate, marginal_tax_rate
import openfisca_france


TaxBenefitSystem = openfisca_france.init_country()
tax_benefit_system = TaxBenefitSystem()


def test_average_tax_rate():
    year = 2013
    simulation = tax_benefit_system.new_scenario().init_single_entity(
        axes = [
            dict(
                count = 100,
                name = 'sali',
                max = 24000,
                min = 0,
            ),
        ],
        period = periods.period('year', year),
        parent1 = dict(agem = 40 * 12 + 6),
        ).new_simulation(debug = True)
    assert (average_tax_rate(simulation, target_column_name = 'revdisp', varying_column_name = 'revdisp') == 0).all()


def test_marginal_tax_rate():
    year = 2013
    simulation = tax_benefit_system.new_scenario().init_single_entity(
        axes = [
            dict(
                count = 10000,
                name = 'sali',
                max = 1000000,
                min = 0,
            ),
        ],
        period = periods.period('year', year),
        parent1 = dict(agem = 40 * 12 + 6),
        ).new_simulation(debug = True)
    assert (marginal_tax_rate(simulation, target_column_name = 'revdisp', varying_column_name = 'revdisp') == 0).all()


if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(level = logging.ERROR, stream = sys.stdout)
    test_marginal_tax_rate()
    test_average_tax_rate()
