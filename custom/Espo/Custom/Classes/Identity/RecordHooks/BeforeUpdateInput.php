<?php

namespace Espo\Custom\Classes\Identity\RecordHooks;

use Espo\Core\Record\Hook\UpdateHook;
use Espo\Core\Record\UpdateParams;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001R: Record update hook (recordDefs beforeUpdateHookClassNameList): refuses link lists that only the link routes may change.
 * All rules live in IdentityGuard. No administrator or service-account exemption.
 *
 * @implements UpdateHook<Entity>
 */
class BeforeUpdateInput implements UpdateHook
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function process(Entity $entity, UpdateParams $params): void
    {
        $this->guard->refuseLinkListInput($entity);
    }
}
