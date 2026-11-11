# CRM-008-G, round 1: Engineer

- **Worktree:** `/srv/CRM/worktrees/CRM-008-G`, branch `forge/CRM-008-G`. The expected HEAD is `f26ad4eaa0f88f02d9ba0f42b4d706efe44275b5`, the CRM-008-F delivery record. Confirm it first. Do not modify `.forge/`.
- **Work order:** `/srv/CRM/main/work-orders/CRM-008-G.md` v1.0. Its facts were probe-verified by the PL on crm-dev. Keep to its allowlist.
- **Reference extractor:** copy `/srv/CRM/worktrees/.forge-scratch/CRM-006R/ref/` and change `CONTRACT_VERSION` from 3 to 4. Use the full selftest for A2.
- **Time box:** 30 minutes; return by about 25. Report `STATUS: completed` with Known gaps if needed.

## The PL's probe hook (verified working; refine it as WO item 2 requires)
```php
<?php
namespace Espo\Custom\Hooks\Task;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class PreserveSalesforceCompletedDate implements BeforeSave
{
    public static int $order = 20;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $sf = $entity->get('sfCompletedAt');
        if ($sf && $entity->get('status') === 'Completed') {
            $entity->set('dateCompleted', $sf);
        }
    }
}
```
**Refinement:** apply it only when `$entity->isNew() || $entity->isAttributeChanged('sfCompletedAt')`, so a staff re-completion gets core's "now". Follow the conventions of the existing custom hooks (see `Hooks/Email/ProtectArchivedEmail.php`) and their static tests in `tests/unit`.

Run both suites, report exact counts, give mutation evidence per WO item, and report the A2 numbers. Finish in the Engineer final message format.
