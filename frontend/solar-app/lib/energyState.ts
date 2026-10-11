const FLOW_W = 20;

export interface EnergyFlows {
  pvWatt: number;
  houseWatt: number;
  gridWatt: number;
  battWatt: number;
  battSoc: number;
}

/**
 * One label for the live flow. Battery and grid signs follow the API:
 * battery > 0 charges, grid > 0 imports.
 */
export function energyState({ pvWatt, houseWatt, gridWatt, battWatt, battSoc }: EnergyFlows): string {
  const generating = pvWatt > FLOW_W;
  const charging = battWatt > FLOW_W;
  const discharging = battWatt < -FLOW_W;
  const importing = gridWatt > FLOW_W;
  const exporting = gridWatt < -FLOW_W;

  if (battSoc >= 99 && !discharging && !importing && houseWatt - pvWatt < 100) {
    return "Fully charged";
  }
  if (exporting && Math.abs(gridWatt) >= Math.abs(battWatt)) return "Exporting";
  if (discharging && generating) return "Solar + battery";
  if (discharging) return "Battery → home";
  if (importing && gridWatt > pvWatt) return "Grid import";
  if (charging && generating) return "Charging";
  if (generating) return "Generating";
  if (importing) return "Grid import";
  return "Idle";
}

export function energyStateClass(state: string): string {
  if (state === "Grid import") return "text-rose-300";
  if (state === "Exporting" || state === "Fully charged") return "text-emerald-300";
  if (state === "Battery → home") return "text-purple-300";
  if (state === "Idle") return "text-zinc-400";
  return "text-amber-300";
}
