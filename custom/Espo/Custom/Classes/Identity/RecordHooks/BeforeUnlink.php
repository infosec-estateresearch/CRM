<?php

namespace Espo\Custom\Classes\Identity\RecordHooks;

use Espo\Core\Record\Hook\UnlinkHook;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001R: Record unlink hook (recordDefs beforeUnlinkHookClassNameList): refuses a successor removed by unlinking and the removal of a contact's primary firm link.
 * All rules live in IdentityGuard. No administrator or service-account exemption.
 *
 * @implements UnlinkHook<Entity>
 */
class BeforeUnlink implements UnlinkHook
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function process(Entity $entity, string $link, Entity $foreignEntity): void
    {
        $this->guard->refuseLinkChange($entity, $link, $foreignEntity, false);
    }
}
