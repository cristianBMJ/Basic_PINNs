# Basic Physics-Informed Neural Networs implementation
from collections import OrderedDict
from typing import Callable
from typing import Union

import torch
from torch import nn
from torch.func import functional_call, grad, vmap

class LinearNN( nn.Module):
    def __init__(
        self,
        num_inputs: int = 1,
        num_layers: int = 1,
        num_neurons: int = 5,
        act: nn.Module  = nn.Tanh(),
    ) -> None:
        """
        Basic neural network architecture with linear layers

        Args:
        num_inputs (int, optional): the dimensionality of the input tensor
        num_layers (int, optional): the number of hidden layers
        num_neurons (int, optional): the number of neurons
        act (int, optional): the nonlinear activation function to use stitching
        """
        super().__init__()
        self.num_inputs = num_inputs
        self.num_layers = num_layers
        self.num_neurons = num_neurons

        layers = []

        # input layer
        layers.append(nn.Linear(self.num_inputs, self.num_neurons)) 

        # hidden layers with linear layer and activation
        for _ in range(num_layers):
            layers.extend([nn.Linear(num_neurons, num_neurons), act])

        # output layer
        layers.append(nn.Linear(num_neurons, 1))

        # build the network
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x.reshape(-1,1)).squeeze()

def make_forward_fn(
        model: nn.Module,
        derivative_order: int = 1,
) -> list[Callable]:
    """
    Make a functional forward pass gradient functions given an input model

    This function creates a set of functional calls of  the input model

    It returns list of composable v-mapped version of  the forward pass
    and of higher-order derivatives with  respect to the inputs as specified
    by the input argument `derivative_order`

    Args:
        model (nn.Module): the model to make the functional calls for.It can be          any subclass of a nn.Module
        
        derivative_order (int, optional): up to which order return functions for
        computing the derivate of the model with respect to the inputs

    Returns:
        List[Callable]; A list of funcitons where each element corresponds to a 
        v-mapped version of the model forward pass and its derivates. The 0-th
        element is always the dorward  pass  and, depending on the value of the
        `derivate_order` argument , the following elements corresponds to  the 
        i-th order derivate function with respect to the model inputs.
        The vmap ensures effiecient support for batched inputs
    """


    def f(x: torch.Tensor, params: Union[dict[str, torch.nn.Parameter], tuple[torch.nn.Parameter, ...]]) -> torch.Tensor:
#    def f(x: torch.Tensor, params: dict[str, torch.nn.Parameter] | tuple[ torch.nn.Parameter, ... ]) -> torch.Tensor: # | indicate that can accept distint parames
        # the functional optimizer works with parameters represented as a tuple instead
        # of the dictionary form required by the `functional_call` API 
        # here we perform the conversion from tuple to dictionary
        if isinstance(params, tuple):
            params_dict = tuple_to_dict_parameters(model, params)
        else:
            params_dict = params

        return functional_call(model, params_dict, (x,))

    fns = []
    fns.append(f)

    dfun = f
    for _ in range(derivative_order):
        # first cumpute the derivate function
        dfun = grad(dfun)

        # the use vmap to support batching
        dfun_vmap = vmap(dfun, in_dims=(0,None))

        fns.append(dfun_vmap)

    return fns

def tuple_to_dict_parameters(
        model: nn.Module, params: tuple[torch.nn.Parameter, ...]
) -> OrderedDict[str, torch.nn.Parameter]:
    """Convert a set of parameters stored as a tuple into a dictionary form

    This conversion is required to be able to call the `functional_call` API which requires
    parameters in a dictionary form from the results of a functional optimization step which 
    returns the parameters as a tuple

    Args:
        model (nn.Module): the model to make the functional calls for. It can be any subclass of
            a nn.Module
        params (tuple[Parameter, ...]): the model parameters stored as a tuple
    
    Returns:
        An OrderedDict instance with the parameters stored as an ordered dictionary
    """
    keys = list(dict(model.named_parameters()).keys())
    values = list(params)
    return OrderedDict(({k:v for k,v in zip(keys, values)}))
    
if __name__ == "__main__":

    # TODO: turn this into a unit test
    
    model = LinearNN(num_layers=2)
    fns = make_forward_fn(model, derivative_order=2)

    batch_size = 10
    x = torch.randn(batch_size)
    # params = dict(model.named_parameters())
    params = dict(model.named_parameters())

    fn_x = fns[0](x, params)
    assert fn_x.shape[0] == batch_size

    dfn_x = fns[1](x, params)
    assert dfn_x.shape[0] == batch_size

    ddfn_x = fns[2](x, params)
    assert ddfn_x.shape[0] == batch_size
