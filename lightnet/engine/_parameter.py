#
#   HyperParemeters container class
#   Copyright EAVISE
#

import torch
import logging
from collections import Iterable

__all__ = ['HyperParameters']
log = logging.getLogger(__name__)


class HyperParameters:
    """ This class is a container for training hyperparameters.
    It allows to save the state of a training and reload it at a later stage.

    Args:
        network (torch.nn.Module): Network module
        optimizers (torch.optim.Optimizer or list of torch.optim.Optimizer, optional): Optimizer(s) for the network; Default **None**
        schedulers (torch.optim._LRScheduler or list of torch.optim._LRScheduler, optional): Scheduler(s) for the network; Default; **None**
        batch_size (int, optional): Size of a batch for training; Default **1**
        mini_batch_size (int, optional): Size of a mini-batch for training; Default **batch_size**
        **kwargs (dict, optional): Keywords arguments that will be set as attributes of the instance and serialized as well

    Attributes:
        self.batch: Number of batches processed; Gets initialized to **0**
        self.epoch: Number of epochs processed; Gets initialized to **0**

    Note:
        If you pass a ``kwarg`` that starts with an **_**,
        the parameter class will store it as a regular property without the leading **_**, but it will not serialize this variable.
        This allows you to store all parameters in this object, regardless of whether you want to serialize it.

    Warning:
        The :class:`~torch.optim.lr_scheduler.ReduceLROnPlateau` LR scheduler does not follow the regular LR scheduler classes.
        Therefore this class will not work with this HyperParameter function.
        If you are using this class, save it as a regular variable, through another name (via kwargs). |br|
        I know this solution is suboptimal, but I am not willing to hack around this, as I believe this is something dirty in the torch codebase itself and should be handled there.

    Note:
        ``batch_size`` must be a multiple of ``mini_batch_size``.
    """
    def __init__(self, network, optimizers=None, schedulers=None, batch_size=1, mini_batch_size=None, **kwargs):
        self.network = network
        self.batch_size = batch_size
        self.batch = 0
        self.epoch = 0

        if mini_batch_size is None or mini_batch_size > batch_size:
            self.mini_batch_size = batch_size
        elif batch_size % mini_batch_size != 0:
            raise ValueError('batch_size should be a multiple of mini_batch_size')
        else:
            self.mini_batch_size = mini_batch_size

        if optimizers is None or isinstance(optimizers, Iterable):
            self.optimizers = optimizers
        else:
            self.optimizers = [optimizers]

        if schedulers is None or isinstance(schedulers, Iterable):
            self.schedulers = schedulers
        else:
            self.schedulers = [schedulers]

        self.__no_serialize = ['network', 'optimizers', 'schedulers']
        for key in kwargs:
            if key.startswith('_'):
                val = kwargs[key]
                key = key[1:]
                self.__no_serialize.append(key)
            else:
                val = kwargs[key]

            if not hasattr(self, key):
                setattr(self, key, val)
            else:
                log.warn(f'{key} attribute already exists as a HyperParameter and will not be overwritten.')
                if key in self.__no_serialize:
                    self.__no_serialize.remove(key)

    @property
    def optimizer(self):
        return self.optimizers[0]

    @property
    def scheduler(self):
        return self.schedulers[0]

    @property
    def batch_subdivisions(self):
        return self.batch_size // self.mini_batch_size

    def save(self, filename):
        state = {k: v for k, v in vars(self).items() if k not in self.__no_serialize}

        state['network'] = self.network.state_dict()
        if self.optimizers is not None:
            state['optimizers'] = [optim.state_dict() for optim in self.optimizers]
        if self.schedulers is not None:
            state['schedulers'] = [sched.state_dict() for sched in self.schedulers]

        torch.save(state, filename)

    def load(self, filename, strict=False):
        state = torch.load(filename, lambda storage, loc: storage)

        self.network.load_state_dict(state.pop('network'), strict=strict)
        if self.optimizers is not None:
            optim_state = state.pop('optimizers')
            for i, optim in enumerate(self.optimizers):
                optim.load_state_dict(optim_state[i])
        if self.schedulers is not None:
            sched_state = state.pop('schedulers')
            for i, sched in enumerate(self.schedulers):
                sched.load_state_dict(sched_state[i])

        for key, value in state.items():
            setattr(self, key, value)

    def to(self, device):
        self.network.to(device)

        for optim in self.optimizers:
            for param in optim.state.values():
                if isinstance(param, torch.Tensor):
                    param.data = param.data.to(device)
                    if param._grad is not None:
                        param._grad.data = param._grad.data.to(device)
                elif isinstance(param, dict):
                    for subparam in param.values():
                        if isinstance(subparam, torch.Tensor):
                            subparam.data = subparam.data.to(device)
                            if subparam._grad is not None:
                                subparam._grad.data = subparam._grad.data.to(device)

        for sched in self.schedulers:
            for param in sched.__dict__.values():
                if isinstance(param, torch.Tensor):
                    param.data = param.data.to(device)
                    if param._grad is not None:
                        param._grad.data = param._grad.data.to(device)
