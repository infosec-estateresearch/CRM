<?php

namespace Espo\Custom\Classes\Identity\RecordHooks;

use Espo\Core\Record\CreateParams;
use Espo\Core\Record\Hook\CreateHook;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001R: Record create hook (recordDefs beforeCreateHookClassNameList): refuses link lists that only the link routes may change.
 * All rules live in IdentityGuard. No administrator or service-account exemption.
 *
 * @implements CreateHook<Entity>
 */
class BeforeCreateInput implements CreateHook
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function process(Entity $entity, CreateParams $params): void
    {
        $this->guard->refuseLinkListInput($entity);
    }
}
