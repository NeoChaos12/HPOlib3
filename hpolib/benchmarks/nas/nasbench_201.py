"""
Interface to Benchmarks with Nas-Bench 201

https://github.com/D-X-Y/AutoDL-Projects/blob/master/docs/NAS-Bench-201.md

How to use this benchmark:
--------------------------

We recommend using the containerized version of this benchmark.
If you want to use this benchmark locally (without running it via the corresponding container),
you need to perform the following steps.


1. Clone and install
====================
Since the data is downloaded automatically, you dont have to do anything but installing the hpolib.

Recommend: ``Python >= 3.6.0``

```
cd /path/to/HPOlib3
pip install .
```

For more info about the nasbench201, please have a look at
https://github.com/D-X-Y/AutoDL-Projects/blob/master/docs/NAS-Bench-201.md
"""
import logging
from typing import Union, Dict, List, Text, Tuple
from copy import deepcopy

import ConfigSpace as CS
import numpy as np

import hpolib.util.rng_helper as rng_helper
from hpolib.abstract_benchmark import AbstractBenchmark
from hpolib.util.data_manager import NASBench_201Data

__version__ = '0.0.1'
MAX_NODES = 4

logger = logging.getLogger('NASBENCH201')


class NasBench201BaseBenchmark(AbstractBenchmark):
    def __init__(self, dataset: str,
                 rng: Union[np.random.RandomState, int, None] = None, **kwargs):
        """
        Benchmark interface to the NASBench201 Benchmarks. The NASBench201 contains
        results for architectures on 4 different data sets.

        We have split the "api" file from NASBench201 in separate files per data set.
        The original "api" file contains all data sets, but loading this single file took too much RAM.

        We recommend to not call this base class directly but using the correct subclass below.

        The parameter ``dataset`` indicates which data set was used for training.

        For each data set the metrics
        'train_acc1es', 'train_losses', 'train_times', 'eval_acc1es', 'eval_times', 'eval_losses' are available.
        However, the data sets report them on different data splits (train, train + valid, test, valid or test+valid).

        Note:
        - The parameter epoch is 0 indexed!
        - In the original data, the training splits are always marked with the key 'train' but they use different
          identifiers to refer to the available evaluation splits. We report them also in the table below.

        The table in the following shows the mapping from data set and metric to used split.

        |-------------------|---------------|-----------------------------------|
        | Data set          | train_*       | eval_*        (key in orig. data) |
        |-------------------|---------------|-----------------------------------|
        | 'cifar10-valid'   | train         | valid         (x-valid)           |
        | 'cifar10'         | train + valid | test          (ori-test)          |
        | 'cifar100'        | train         | valid + test  (ori-test)          |
        | 'ImageNet16-120'  | train         | valid + test  (ori-test)          |
        |-------------------|---------------|-----------------------------------|


        Some further remarks:
        - cifar10-valid is trained on the train split and tested on the validation split.
        - cifar10 is trained on the train *and* validation split and tested on the test split.
        - The train metrics are dictionaries with epochs (e.g. 0, 1, 2) as key and the metric as value.
          The evaluation metrics, however, have as key the identifiers, e.g. ori-test@0, with 0 indicating the epoch.
          Also, each data set (except for cifar10) reports values for all 200 epochs for a metric on the specified
          split (see first table) and a single value on the 200th epoch for the other splits.
          Table 3 shows the available identifiers for each data set.

        |-------------------|------------------------------|
        | Data set          | eval*:   values for epochs   |
        |-------------------|------------------------------|
        | 'cifar10-valid'   | x-valid:	0-199	           |
        |		     		| ori-test:	199		           |
        | 'cifar10'         | ori-test:	0-199	           |
        | 'cifar100'        | ori-test:	0-199	           |
        |					| x-valid:	199		           |
        |   				| x-test:   199                |
        | 'ImageNet16-120'  | ori-test:	0-199	           |
        |					| x-valid:	199		           |
        |   				| x-test:  	199                |
        |-------------------|------------------------------|

        Parameters
        ----------
        dataset : str
            One of cifar10-valid, cifar10, cifar100, ImageNet16-120.
        rng : np.random.RandomState, int, None
            Random seed for the benchmark's random state.
        """

        super(NasBench201BaseBenchmark, self).__init__(rng=rng)

        data_manager = NASBench_201Data(dataset=dataset)

        self.data = data_manager.load()

        self.config_to_structure = NasBench201BaseBenchmark.config_to_structure_func(max_nodes=MAX_NODES)

    @AbstractBenchmark._configuration_as_dict
    @AbstractBenchmark._check_configuration
    @AbstractBenchmark._check_fidelity
    def objective_function(self, configuration: Union[CS.Configuration, Dict],
                           fidelity: Union[Dict, None] = None,
                           rng: Union[np.random.RandomState, int, None] = None,
                           data_seed: Union[List, Tuple, int, None] = (777, 888, 999),
                           **kwargs) -> Dict:
        """
        Objective function for the NASBench201 benchmark.
        This functions sends a query to NASBench201 and evaluates the configuration.
        As already explained in the class definition, different data sets are trained on different splits. For example
        cifar10 is trained on the train and validation split and tested on the test split. Therefore, different entries
        are returned from the NASBench201 result.

        Overview of the used splits for training and testing and which are returned in the objective_function and
        which in the objective_function_test.

        |-------------------|-----------------------|---------------------------|
        |                   | Returned by           | Returned by               |
        |                   |   objective_function  |   objective_function_test |
        | Data set          | train_*               | eval_*                    |
        |-------------------|-----------------------|---------------------------|
        | 'cifar10-valid'   | train                 | valid                     |
        | 'cifar10'         | train + valid         | test                      |
        | 'cifar100'        | train                 | valid + test              |
        | 'ImageNet16-120'  | train                 | valid + test              |
        |-------------------|-----------------------|---------------------------|

        Legend:
        * = [losses, acc1es, times]

        Parameters
        ----------
        configuration
        fidelity: Dict, None
            epoch: int - Values: [0, 199]
                Number of epochs an architecture was trained.
                Note: the number of epoch is 0 indexed! (Results after the first epoch: epoch = 0)

            Fidelity parameters, check get_fidelity_space(). Uses default (max) value if None.
        rng : np.random.RandomState, int, None
            Random seed to use in the benchmark.

            To prevent overfitting on a single seed, it is possible to pass a
            parameter ``rng`` as 'int' or 'np.random.RandomState' to this function.
            If this parameter is not given, the default random state is used.
        data_seed : List, Tuple, None, int
            The nasbench_201 benchmark include for each run 3 different seeds: 777, 888, 999.
            The user can specify which seed to use. If more than one seed is given, the results are averaged
            across the seeds but then the time needed for training is the sum of the costs per seed.
            Note:
                For some architectures (configurations) no run was available. We've set missing values to an
                available value from another seed. Therefore, it is possible that run results are exactly the same for
                different seeds.

        kwargs

        Returns
        -------
        Dict -
            function_value : training precision
            cost : time to train the network
            info : Dict
                train_precision : float
                train_losses : float
                train_cost : float
                    Time needed to train the network for 'epoch' many epochs. If more than one seed is given,
                    this field is the sum of the training time per network
                eval_precision : float
                eval_losses : float
                eval_cost : float
                    Time needed to train the network for 'epoch many epochs plus the time to evaluate the network on the
                    evaluation split. If more than one seed is given, this field is the sum of the eval cost per network
                fidelity : Dict
                    used fidelities in this evaluation
        """

        # Check if the data set seeds are valid
        assert isinstance(data_seed, List) or isinstance(data_seed, Tuple) or isinstance(data_seed, int), \
            f'data seed has unknown data type {type(data_seed)}, but should be tuple or int (777,888,999)'

        if isinstance(data_seed, List):
            data_seed = tuple(data_seed)

        if isinstance(data_seed, int):
            data_seed = (data_seed, )

        assert len(set(data_seed) - {777, 888, 999}) == 0,\
            f'data seed can only contain the elements 777, 888, 999, but was {data_seed}'

        self.rng = rng_helper.get_rng(rng)

        structure = self.config_to_structure(configuration)
        structure_str = structure.tostr()

        epoch = fidelity['epoch']

        train_accuracies = [self.data[(seed, 'train_acc1es')][structure_str][epoch] for seed in data_seed]
        train_losses = [self.data[(seed, 'train_losses')][structure_str][epoch] for seed in data_seed]
        train_times = [np.sum(self.data[(seed, 'train_times')][structure_str][:epoch + 1]) for seed in data_seed]

        eval_accuracies = [self.data[(seed, 'eval_acc1es')][structure_str][epoch] for seed in data_seed]
        eval_losses = [self.data[(seed, 'eval_losses')][structure_str][epoch] for seed in data_seed]
        eval_times = [np.sum(self.data[(seed, 'eval_times')][structure_str][:epoch + 1]) for seed in data_seed]

        return {'function_value': float(100 - np.mean(train_accuracies)),
                'cost': float(np.sum(train_times)),
                'info': {'train_precision': float(100 - np.mean(train_accuracies)),
                         'train_losses': float(np.mean(train_losses)),
                         'train_cost': float(np.sum(train_times)),
                         'eval_precision': float(100 - np.mean(eval_accuracies)),
                         'eval_losses': float(np.mean(eval_losses)),
                         'eval_cost': float(np.sum(train_times)) + float(np.sum(eval_times)),
                         'fidelity': fidelity
                         }
                }

    @AbstractBenchmark._configuration_as_dict
    @AbstractBenchmark._check_configuration
    def objective_function_test(self, configuration: Union[CS.Configuration, Dict],
                                fidelity: Union[Dict, None] = None,
                                rng: Union[np.random.RandomState, int, None] = None,
                                **kwargs) -> Dict:
        """
        Get the validated results from the NASBench201. Runs a given configuration on the largest budget (here: 199).
        The test function uses all data set seeds (777, 888, 999).

        See also :py:meth:`~hpolib.benchmarks.nas.nasbench_201.objective_function`

        Parameters
        ----------
        configuration
        fidelity: Dict, None
            epoch: int - Values: [0, 199]
                Number of epochs an architecture was trained.
                Note: the number of epoch is 0 indexed! (Results after the first epoch: epoch = 0)

            Fidelity parameters, check get_fidelity_space(). Uses default (max) value if None.
        rng : np.random.RandomState, int, None
            Random seed to use in the benchmark.

            To prevent overfitting on a single seed, it is possible to pass a
            parameter ``rng`` as 'int' or 'np.random.RandomState' to this function.
            If this parameter is not given, the default random state is used.

        kwargs

        Returns
        -------
        Dict -
            function_value : evaluation precision
            cost : time to the network + time to validate
            info : Dict
                train_precision
                train_losses
                train_cost
                eval_precision
                eval_losses
                eval_cost
                fidelity : used fidelities in this evaluation
        """

        # The result dict should contain already all necessary information -> Just swap the function value from valid
        # to test and the corresponding time cost
        result = self.objective_function(configuration=configuration, fidelity=fidelity, data_seed=(777, 888, 999),
                                         rng=rng, **kwargs)
        result['function_value'] = result['info']['eval_precision']
        result['cost'] = result['info']['eval_cost']
        return result

    @staticmethod
    def config_to_structure_func(max_nodes: int):
        # From https://github.com/D-X-Y/AutoDL-Projects/blob/master/exps/algos/BOHB.py
        # Author: https://github.com/D-X-Y [Xuanyi.Dong@student.uts.edu.au]
        def config_to_structure(config):
            genotypes = []
            for i in range(1, max_nodes):
                x_list = []
                for j in range(i):
                    node_str = f'{i}<-{j}'
                    op_name = config[node_str]
                    x_list.append((op_name, j))
                genotypes.append(tuple(x_list))
            return NasBench201BaseBenchmark._Structure(genotypes)
        return config_to_structure

    @staticmethod
    def get_search_spaces(xtype: str, name: str) -> List[Text]:
        # obtain the search space, i.e., a dict mapping the operation name into a python-function for this op
        # From https://github.com/D-X-Y/AutoDL-Projects/blob/master/lib/models/__init__.py
        # Author: https://github.com/D-X-Y [Xuanyi.Dong@student.uts.edu.au]
        if xtype == 'cell':
            NAS_BENCH_201 = ['none', 'skip_connect', 'nor_conv_1x1', 'nor_conv_3x3', 'avg_pool_3x3']
            SearchSpaceNames = {'nas-bench-201': NAS_BENCH_201}
            assert name in SearchSpaceNames, 'invalid name [{:}] in {:}'.format(name, SearchSpaceNames.keys())
            return SearchSpaceNames[name]
        else:
            raise ValueError('invalid search-space type is {:}'.format(xtype))

    @staticmethod
    def get_configuration_space(seed: Union[int, None] = None) -> CS.ConfigurationSpace:
        """
        Return the CS representation of the search space.
        From https://github.com/D-X-Y/AutoDL-Projects/blob/master/exps/algos/BOHB.py
        Author: https://github.com/D-X-Y [Xuanyi.Dong@student.uts.edu.au]

        Parameters
        ----------
        seed : int, None
            Random seed for the configuration space.

        Returns
        -------
        CS.ConfigurationSpace -
            Containing the benchmark's hyperparameter
        """
        seed = seed if seed is not None else np.random.randint(1, 100000)
        cs = CS.ConfigurationSpace(seed=seed)

        search_space = NasBench201BaseBenchmark.get_search_spaces('cell', 'nas-bench-201')
        hps = [CS.CategoricalHyperparameter(f'{i}<-{j}', search_space) for i in range(1, MAX_NODES) for j in range(i)]
        cs.add_hyperparameters(hps)
        return cs

    @staticmethod
    def get_fidelity_space(seed: Union[int, None] = None) -> CS.ConfigurationSpace:
        """
        Creates a ConfigSpace.ConfigurationSpace containing all fidelity parameters for
        the NAS Benchmark 201.

        Fidelities:
         - epoch: int
         The loss / accuracy at `epoch`. Can be from 0 to 199.

        Parameters
        ----------
        seed : int, None
            Fixing the seed for the ConfigSpace.ConfigurationSpace

        Returns
        -------
        ConfigSpace.ConfigurationSpace
        """
        seed = seed if seed is not None else np.random.randint(1, 100000)
        fidel_space = CS.ConfigurationSpace(seed=seed)

        fidel_space.add_hyperparameters([
            CS.UniformIntegerHyperparameter('epoch', lower=0, upper=199, default_value=199)
        ])

        return fidel_space

    @staticmethod
    def get_meta_information() -> Dict:
        """ Returns the meta information for the benchmark """
        return {'name': 'NAS-Bench-201',
                'references': ['Xuanyi Dong, Yi Yang',
                               'NAS-Bench-201: Extending the Scope of Reproducible Neural Architecture Search',
                               'https://openreview.net/forum?id=HJxyZkBKDr',
                               'https://github.com/D-X-Y/AutoDL-Projects'],
                }

    class _Structure:
        def __init__(self, genotype):
            assert isinstance(genotype, list) or isinstance(genotype, tuple), 'invalid class of genotype : {:}'.format(
                type(genotype))
            self.node_num = len(genotype) + 1
            self.nodes = []
            self.node_N = []
            for idx, node_info in enumerate(genotype):
                assert isinstance(node_info, list) or isinstance(node_info,
                                                                 tuple), 'invalid class of node_info : {:}'.format(
                    type(node_info))
                assert len(node_info) >= 1, 'invalid length : {:}'.format(len(node_info))
                for node_in in node_info:
                    assert isinstance(node_in, list) or isinstance(node_in,
                                                                   tuple), 'invalid class of in-node : {:}'.format(
                        type(node_in))
                    assert len(node_in) == 2 and node_in[1] <= idx, 'invalid in-node : {:}'.format(node_in)
                self.node_N.append(len(node_info))
                self.nodes.append(tuple(deepcopy(node_info)))

        def tostr(self):
            strings = []
            for node_info in self.nodes:
                string = '|'.join([x[0] + '~{:}'.format(x[1]) for x in node_info])
                string = '|{:}|'.format(string)
                strings.append(string)
            return '+'.join(strings)

        def __repr__(self):
            return (
                '{name}({node_num} nodes with {node_info})'.format(name=self.__class__.__name__, node_info=self.tostr(),
                                                                   **self.__dict__))

        def __len__(self):
            return len(self.nodes) + 1

        def __getitem__(self, index):
            return self.nodes[index]


class Cifar10NasBench201Benchmark(NasBench201BaseBenchmark):

    def __init__(self, rng: Union[np.random.RandomState, int, None] = None, **kwargs):
        super(Cifar10NasBench201Benchmark, self).__init__(dataset='cifar10', rng=rng, **kwargs)


class Cifar10ValidNasBench201Benchmark(NasBench201BaseBenchmark):

    def __init__(self, rng: Union[np.random.RandomState, int, None] = None, **kwargs):
        super(Cifar10ValidNasBench201Benchmark, self).__init__(dataset='cifar10-valid', rng=rng, **kwargs)


class Cifar100NasBench201Benchmark(NasBench201BaseBenchmark):

    def __init__(self, rng: Union[np.random.RandomState, int, None] = None, **kwargs):
        super(Cifar100NasBench201Benchmark, self).__init__(dataset='cifar100', rng=rng, **kwargs)


class ImageNetNasBench201Benchmark(NasBench201BaseBenchmark):

    def __init__(self, rng: Union[np.random.RandomState, int, None] = None, **kwargs):
        super(ImageNetNasBench201Benchmark, self).__init__(dataset='ImageNet16-120', rng=rng, **kwargs)
