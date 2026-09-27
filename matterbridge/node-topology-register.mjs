// matterbridge-mqtt creates the mandatory PowerTopology cluster for an
// ElectricalSensor with TREE topology. This meter represents the entire home,
// not a child endpoint tree, so advertise NODE topology for this device only.
import {
  MatterbridgeEndpoint,
} from "/usr/local/lib/node_modules/matterbridge/dist/export.js";
import { PowerTopology } from "/usr/local/lib/node_modules/matterbridge/node_modules/@matter/types/dist/esm/clusters/power-topology.js";

const targetDeviceId = process.env.MATTERBRIDGE_NODE_TOPOLOGY_DEVICE_ID;
const createPowerTopology =
  MatterbridgeEndpoint.prototype.createDefaultPowerTopologyClusterServer;

MatterbridgeEndpoint.prototype.createDefaultPowerTopologyClusterServer =
  function createWholeHomePowerTopology(
    feature = PowerTopology.Feature.TreeTopology,
    availableEndpoints = [],
    activeEndpoints = [],
  ) {
    if (
      targetDeviceId &&
      this.originalId === targetDeviceId &&
      feature === PowerTopology.Feature.TreeTopology
    ) {
      console.info(
        `[node-topology-register] ${targetDeviceId}: TreeTopology -> NodeTopology`,
      );
      feature = PowerTopology.Feature.NodeTopology;
    }

    return createPowerTopology.call(
      this,
      feature,
      availableEndpoints,
      activeEndpoints,
    );
  };
