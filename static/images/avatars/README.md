# Avatar SVG Files

## Directory Structure

### Bud (Control Character)
Place Bud SVG files in: `bud/`
- `bud-smiling.svg` - Default smiling state (no messages)
- `bud-talking.svg` - Talking animation state (for future use)

### Spud (Treatment Character)
Place Spud SVG files in subdirectories based on plant state:

#### Base (Healthy Plant) - `spud/base/`
For prompt counts 0-2:
- `spud-base-smiling.svg`
- `spud-base-talking.svg`
- `spud-base-welling.svg`
- `spud-base-sad.svg`
- `spud-base-sad-talking.svg`
- `spud-base-crying.svg`

#### Yellow (Plant Wilting) - `spud/yellow/`
For prompt counts 3-5:
- `spud-yellow-smiling.svg`
- `spud-yellow-talking.svg`
- `spud-yellow-welling.svg`
- `spud-yellow-sad.svg`
- `spud-yellow-sad-talking.svg`
- `spud-yellow-crying.svg`

#### Dry (Plant Fully Wilted) - `spud/dry/`
For prompt counts 6+:
- `spud-dry-smiling.svg`
- `spud-dry-talking.svg`
- `spud-dry-welling.svg`
- `spud-dry-sad.svg`
- `spud-dry-sad-talking.svg`
- `spud-dry-crying.svg`

## Naming Convention
All files should follow the pattern:
- Bud: `bud-{state}.svg`
- Spud: `spud-{plantState}-{animationState}.svg`

Where:
- `plantState` = `base`, `yellow`, or `dry`
- `animationState` = `smiling`, `talking`, `welling`, `sad`, `sad-talking`, or `crying`

## File Requirements
- SVG format
- Optimized for web (remove unnecessary metadata)
- Consistent sizing (recommended: 200x200px viewBox)
- Transparent background preferred

