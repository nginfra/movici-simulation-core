# More WNTR Research results
This directory contains a number of Jupyter Notebooks to validate the workings
of various components in WNTR drinking water simulations. These notebooks may
be removed before completing integration of the WNTR model into
movici-simulation-core

# Findings

## Flow rates and velocity shenanigans

In WNTR flow rates are dependent on the directionality of the flow. If the 
flow direction is from the "to_node" to the "from_node", then the flow rate
is output as negative. Coversely, the velocity is not dependent on this 
direction and is always positive.

**Action**: We should decide whether to incorporate this behaviour, or to
reverse it. For external users it may be more intuitive that velocity is
directional and flowrate isn't. An alternative for visualization purposes
is that we also publish a `drinking_water.flow_rate.magnitude` attribute
that is always positive

## Link status may be updated by WNTR

The status (OPEN, CLOSED) for links such as pipes and pumps may be changed
by WNTR (even when not adding controls). This has implications about how
to treat this attribute. We probably need to treat this separately from
`operational.status`. Let's introduce a new variable:
`drinking_water.link_status` that is an int/enum attribute (CLOSED, OPEN,
ACTIVE) to match the WNTR status. This then is the PUB attribute for the
drinking water model. We then have `operational.status` that we use in 
the rules model to activate/deactivate links and that is SUB (OPT) in 
the drinking water model. The drinking water model can update the wntr
status, and then when WNTR has finished a calculation, update
`drinking_water.link_status` accordingly.

Manually updating the link status can be done by assigning to the links
`initial_status` property. eg:

```python
wn.get_link("<link-id>").initial_status = "OPEN" if operational_status else "CLOSED"
```

## Check valve block reverse flow

Check valves in pipes are documented to limit flow to a single direction,
but it is not documented which direction. A test has indicated that it
only allows flow in the forward direction (ie. from_node -> to_node). This
matches with what we would expect/assume.

## Tank overflow is not supported

WNTR Tanks have an `overflow` attribute to configure a tank to allow
inflow when the tank is full. Any inflowing water would then be discarded.
However, WNTR does not support this functionality, which is actually
[documented](https://usepa.github.io/WNTR/apidoc/wntr.network.model.WaterNetworkModel.html#wntr.network.model.WaterNetworkModel.add_tank).

## Pumps

Power pumps can be given a different power during a simulation. It is
however not possible to change the speed setting for a HEAD pump. It
alway operates at speed=1 if turned on (OPEN). We therefore do not need
to introduce a `drinking_water.speed` attribute.

## Valves

The following valves are supported by WNTR:

 * PRV (Pressure reducing valve)
 * PSV (Pressure sustaining valve)
 * FCV (Flow control valve)
 * TCV (Throttle control valve)

The following valves are not supported by the WNTRSimulator:
 * PBV (Pressure Breaking Valve)
 * GPV (General Purpose Valve)

Valves have statuses OPEN CLOSED and ACTIVE. Valves seem to be the
only links that use the ACTIVE status. When a valve's `operational.status`
is set to `True`, we should set the valve's status to ACTIVE. WNTR
will internally set the valve to the correct setting depending on 
the valve type


