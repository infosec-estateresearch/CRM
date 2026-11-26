<?php

namespace Espo\Custom\Classes\Identity\RecordHooks;

use Espo\Core\Record\DeleteParams;
use Espo\Core\Record\Hook\DeleteHook;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001R: Record delete hook (recordDefs beforeDeleteHookClassNameList): firms and contacts are never deleted, for any account, administrator included.
 * All rules live in IdentityGuard. No administrator or service-account exemption.
 *
 * @implements DeleteHook<Entity>
 */
class BeforeDelete implements DeleteHook
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function process(Entity $entity, DeleteParams $params): void
    {
        throw $this->guard->removalRefusal();
    }
}
